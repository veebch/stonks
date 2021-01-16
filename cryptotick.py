
from time import sleep
import argparse
from PIL import Image, ImageDraw, ImageFont
from sys import path
from IT8951 import constants
import os, random
import textwrap
import qrcode
import feedparser
import requests
import textwrap
import unicodedata
import re
import logging
import os
import yaml 
import time
import socket
import numpy as np
import matplotlib.pyplot as plt
import currency

dirname = os.path.dirname(__file__)
configfile = os.path.join(os.path.dirname(os.path.realpath(__file__)),'config.yaml')
picdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'images')


def internet(host="8.8.8.8", port=53, timeout=3):
    """
    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        logging.info("No internet")
        return False


def print_system_info(display):
    epd = display.epd

    print('System info:')
    print('  display size: {}x{}'.format(epd.width, epd.height))
    print('  img buffer address: {:X}'.format(epd.img_buf_address))
    print('  firmware version: {}'.format(epd.firmware_version))
    print('  LUT version: {}'.format(epd.lut_version))
    print()

def _place_text(img, text, x_offset=0, y_offset=0,fontsize=40,fontstring="Forum-Regular"):
    '''
    Put some centered text at a location on the image.
    '''

    draw = ImageDraw.Draw(img)

    try:
        filename = os.path.join(dirname, './fonts/'+fontstring+'.ttf')
        font = ImageFont.truetype(filename, fontsize)
    except OSError:
        font = ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf', fontsize)

    img_width, img_height = img.size
    text_width, _ = font.getsize(text)
    text_height = fontsize

    draw_x = (img_width - text_width)//2 + x_offset
    draw_y = (img_height - text_height)//2 + y_offset

    draw.text((draw_x, draw_y), text, font=font,fill=(0,0,0) )

def writewrappedlines(img,text,fontsize,y_text=-300,height=110, width=27,fontstring="Forum-Regular"):
    lines = textwrap.wrap(text, width)
    for line in lines:
        width= 0
        _place_text(img, line,0, y_text, fontsize,fontstring)
        y_text += height
    return img

def clear_display(display):
    print('Clearing display...')
    display.clear()

def beanaproblem(image,message):
#   A visual cue that the wheels have fallen off
    thebean = Image.open(os.path.join(picdir,'thebean.bmp'))
    image.paste(thebean, (60,15))
    writewrappedlines(image, message,fontsize=80, y_text=150,height=100,width=40 ,fontstring="Forum-Regular")
    return image 

def display_image_8bpp(display, img):
    dims = (display.width, display.height)
    img.thumbnail(dims)
    paste_coords = [dims[i] - img.size[i] for i in (0,1)]  # align image with bottom of display
    img=img.rotate(180, expand=True)
    display.frame_buf.paste(img, paste_coords)
    display.draw_full(constants.DisplayModes.GC16)


def getData(config):
    """
    The function to update the ePaper display. There are two versions of the layout. One for portrait aspect ratio, one for landscape.
    """
    crypto_list = currencystringtolist(config['ticker']['currency'])
    fiat_list=currencystringtolist(config['ticker']['fiatcurrency'])
    fiat=fiat_list[0]
    print(fiat)
    logging.info("Getting Data")
    days_ago=int(config['ticker']['sparklinedays'])   
    endtime = int(time.time())
    starttime = endtime - 60*60*24*days_ago
    starttimeseconds = starttime
    endtimeseconds = endtime
    allprices = {}
    # Get the price 
    for whichcoin in crypto_list:
        print(whichcoin)
        geckourl = "https://api.coingecko.com/api/v3/coins/markets?vs_currency="+fiat+"&ids="+whichcoin
        print(geckourl)
        rawlivecoin = requests.get(geckourl).json()
        print(rawlivecoin[0])   
        liveprice = rawlivecoin[0]
        pricenow= float(liveprice['current_price'])
        print("Got Live Data From CoinGecko")
        geckourlhistorical = "https://api.coingecko.com/api/v3/coins/"+whichcoin+"/market_chart/range?vs_currency="+fiat+"&from="+str(starttimeseconds)+"&to="+str(endtimeseconds)
        logging.info(geckourlhistorical)
        rawtimeseries = requests.get(geckourlhistorical).json()
        print("Got price for the last "+str(days_ago)+" days from CoinGecko")
        timeseriesarray = rawtimeseries['prices']
        timeseriesstack = []
        length=len (timeseriesarray)
        i=0
        while i < length:
            timeseriesstack.append(float (timeseriesarray[i][1]))
            i+=1
        timeseriesstack.append(pricenow)
        allprices[whichcoin] = timeseriesstack
    return allprices

def makeSpark(allprices):
    # Draw and save the sparkline that represents historical data

    # Subtract the mean from the sparkline to make the mean appear on the plot (it's really the x axis)    
    for key in allprices.keys():   
        x = allprices[key]-np.mean(allprices[key])

        fig, ax = plt.subplots(1,1,figsize=(10,3))
        plt.plot(x, color='k', linewidth=3)
        plt.plot(len(x)-1, x[-1], color='r', marker='o')

        # Remove the Y axis
        for k,v in ax.spines.items():
            v.set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axhline(c='k', linewidth=2, linestyle=(0, (5, 2, 1, 2)))

        # Save the resulting bmp file to the images directory
        plt.savefig(os.path.join(picdir, key+'spark.png'), dpi=72)
        plt.clf() # Close plot to prevent memory error


def updateDisplay(image,config,allprices):
    """   
    Takes the price data, the desired coin/fiat combo along with the config info for formatting
    if config is re-written following adustment we could avoid passing the last two arguments as
    they will just be the first two items of their string in config 
    """
    crypto_list = currencystringtolist(config['ticker']['currency'])
    fiat_list=currencystringtolist(config['ticker']['fiatcurrency'])
    fiat=fiat_list[0]
    days_ago=int(config['ticker']['sparklinedays'])   
    symbolstring=currency.symbol(fiat.upper())

    if fiat=="jpy":
        symbolstring="¥"
    height=160

    heightincrement=295
    for key in allprices.keys():  
        pricenow = allprices[key][-1]
        whichcoin=key
        currencythumbnail= 'currency/'+whichcoin+'.png'
        tokenfilename = os.path.join(picdir,currencythumbnail)
        sparkpng = Image.open(os.path.join(picdir,key+'spark.png'))
    #   Check for token image, if there isn't one, get on off coingecko, resize it and pop it on a white background
        if os.path.isfile(tokenfilename):
            logging.info("Getting token Image from Image directory")
            tokenimage = Image.open(tokenfilename)
        else:
            print("Getting token Image from Coingecko")
            tokenimageurl = "https://api.coingecko.com/api/v3/coins/"+whichcoin+"?tickers=false&market_data=false&community_data=false&developer_data=false&sparkline=false"
            rawimage = requests.get(tokenimageurl).json()
            tokenimage = Image.open(requests.get(rawimage['image']['large'], stream=True).raw)
            tokenimage = tokenimage.convert("RGBA")
            new_image = Image.new("RGBA", (290,290), "WHITE") # Create a white rgba background with a 10 pizel border
            new_image.paste(tokenimage, (20, 20), tokenimage)   
            tokenimage=new_image
            tokenimage.save(tokenfilename)
        newsize=(200,200)
        tokenimage.thumbnail(newsize,Image.ANTIALIAS) 

        pricechange = str("%+d" % round((allprices[key][-1]-allprices[key][0])/allprices[key][-1]*100,2))+"%"
        if pricenow > 1000:
            pricenowstring =format(int(pricenow),",")
        else:
            pricenowstring =str(float('%.5g' % pricenow))

        draw = ImageDraw.Draw(image)   
 #       draw.text((110,90),str(days_ago)+"day : "+pricechange,font =font_date,fill = 0)
        # Print price to 5 significant figures
        image.paste(sparkpng, (290,height+40))
        image.paste(tokenimage, (120,height+30))

        text=symbolstring+pricenowstring
        _place_text(image, text, x_offset=470, y_offset=height-400,fontsize=120,fontstring="JosefinSans-Light")
        text=str(days_ago)+" day : "+pricechange
        _place_text(image, text, x_offset=470, y_offset=height-320,fontsize=60,fontstring="JosefinSans-Light")
        height += heightincrement
    text=str(time.strftime("%H:%M %a %d %b %Y"))
    _place_text(image, text, x_offset=0, y_offset=-420,fontsize=50,fontstring="JosefinSans-Medium")
    return image


def currencystringtolist(currstring):
    # Takes the string for currencies in the config.yaml file and turns it into a list
    curr_list = currstring.split(",")
    curr_list = [x.strip(' ') for x in curr_list]
    return curr_list

def _place_text(img, text, x_offset=0, y_offset=0,fontsize=40,fontstring="Forum-Regular"):
    '''
    Put some centered text at a location on the image.
    '''

    draw = ImageDraw.Draw(img)

    try:
        filename = os.path.join(dirname, './fonts/'+fontstring+'.ttf')
        font = ImageFont.truetype(filename, fontsize)
    except OSError:
        font = ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf', fontsize)

    img_width, img_height = img.size
    text_width, _ = font.getsize(text)
    text_height = fontsize

    draw_x = (img_width - text_width)//2 + x_offset
    draw_y = (img_height - text_height)//2 + y_offset

    draw.text((draw_x, draw_y), text, font=font,fill=(0,0,0) )

def writewrappedlines(img,text,fontsize,y_text=-300,height=110, width=27,fontstring="Forum-Regular"):
    lines = textwrap.wrap(text, width)
    for line in lines:
        width= 0
        _place_text(img, line,0, y_text, fontsize,fontstring)
        y_text += height
    return img

def clear_display(display):
    print('Clearing display...')
    display.clear()


def nth_repl(s, sub, repl, n):
    find = s.find(sub)
    # If find is not -1 we have found at least one match for the substring
    i = find != -1
    # loop util we find the nth or we find no match
    while find != -1 and i != n:
        # find + 1 means we start searching from after the last match
        find = s.find(sub, find + 1)
        i += 1
    # If i is equal to n we found nth match so replace
    if i == n:
        return s[:find] + repl + s[find+len(sub):]
    return s

def by_size(words, size):
    return [word for word in words if len(word) <= size]


def display_image_8bpp(display, img):

    dims = (display.width, display.height)
    img.thumbnail(dims)
    paste_coords = [dims[i] - img.size[i] for i in (0,1)]  # align image with bottom of display
    img=img.rotate(180, expand=True)
    display.frame_buf.paste(img, paste_coords)
    display.draw_full(constants.DisplayModes.GC16)


def parse_args():
    p = argparse.ArgumentParser(description='Test EPD functionality')
    p.add_argument('-v', '--virtual', action='store_true',
                   help='display using a Tkinter window instead of the '
                        'actual e-paper device (for testing without a '
                        'physical device)')
    p.add_argument('-r', '--rotate', default=None, choices=['CW', 'CCW', 'flip'],
                   help='run the tests with the display rotated by the specified value')
    return p.parse_args()

def currencystringtolist(currstring):
    # Takes the string for currencies in the config.yaml file and turns it into a list
    curr_list = currstring.split(",")
    curr_list = [x.strip(' ') for x in curr_list]
    return curr_list

def main():

    def fullupdate():
        """  
        The steps required for a full update of the display
        Earlier versions of the code didn't grab new data for some operations
        but the e-Paper is too slow to bother the coingecko API 
        """
        try:
            print("FULL UPDATE")
            allprices=getData(config)
            # generate sparkline
            print("SPARKY")
            makeSpark(allprices)
            # update display
            screenimage=updateDisplay(img,config, allprices)
            display_image_8bpp(display, screenimage)
            print(allprices)
            lastgrab=time.time()
            time.sleep(.2)
        except Exception as e:
            message="Data pull/print problem"
            pic = beanaproblem(img,str(e))
            display_image_8bpp(display, pic)
            time.sleep(10)
            lastgrab=lastcoinfetch
        return lastgrab

    args = parse_args()

    if not args.virtual:
        from IT8951.display import AutoEPDDisplay

        print('Initializing EPD...')

        # here, spi_hz controls the rate of data transfer to the device, so a higher
        # value means faster display refreshes. the documentation for the IT8951 device
        # says the max is 24 MHz (24000000), but my device seems to still work as high as
        # 80 MHz (80000000)
        display = AutoEPDDisplay(vcom=-2.69, rotate=args.rotate, spi_hz=24000000)

        print('VCOM set to', display.epd.get_vcom())

    else:
        from IT8951.display import VirtualEPDDisplay
        display = VirtualEPDDisplay(dims=(800, 600), rotate=args.rotate)
    
    img = Image.new("RGB", (1448, 1072), color = (255, 255, 255) )
#   Get the configuration from config.yaml
    with open(configfile) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    datapulled=False
    lastcoinfetch = time.time()
    while True:
        if internet():
            if (time.time() - lastcoinfetch > float(config['ticker']['updatefrequency'])) or (datapulled==False):
                lastcoinfetch=fullupdate()
                datapulled = True
            

if __name__ == '__main__':
    main()
