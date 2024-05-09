# -*- coding: utf-8 -*-

from flask import Flask, Response, render_template, Blueprint, request
import json
import requests
from xml2ass import BilibiliDanmaku
import xml2ass2

app = Flask(__name__)

headers = {
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36"
}

def gettime(t):
    t = int(t*1000)
    h = t // 3600000
    t %= 3600000
    m = t // 60000
    t %=  60000
    s = t // 1000
    ms = t % 1000
    return '{:02d}:{:02d}:{:02d},{:03d}'.format(h, m, s, ms)

def json2srt(url):
    try:
        resp = requests.get(url)
        resp.encoding = 'utf-8'
        data = resp.json()
        body = data["body"]
        srt = ""
        for i, item in enumerate(body):
            srt += str(i+1) + '\n'
            srt += gettime(item['from']) + ' --> ' + gettime(item['to']) + '\n'
            srt += item["content"] + '\n'
        return srt
    except:
        return ""

@app.route("/")
def home():
  return Response("success", mimetype="text/plain")

@app.route("/subtitle", methods=["GET", "POST"])
def subtitle():
    url = getvalue('url')
    if (url):
        srt = json2srt(url)
        return Response(srt, mimetype="text/plain")

    ass = ""
    cid = getvalue('cid')
    if not cid:
        return Response(ass, mimetype="text/plain")

    
    width = isFloat(getvalue("width")) and int(getvalue("width")) or 1920
    height = isFloat(getvalue("height")) and int(getvalue("height")) or 1080
    font = getvalue("font") or "微软雅黑"
    # font = getvalue("font") or "sans-serif"
    fontsize = isFloat(getvalue("font_size")) and float(getvalue("font_size")) or 40.0
    alpha = isFloat(getvalue("alpha")) and float(getvalue("alpha")) or 0.8
    duration_marquee = isFloat(getvalue("duration_marquee")) and float(getvalue("duration_marquee")) or 15.0
    duration_still = isFloat(getvalue("duration_still")) and float(getvalue("duration_still")) or 5.0
    is_reduce_comments = getvalue("is_reduce_comments").upper() == "TRUE"
    display_area = isFloat(getvalue("display_area")) and float(getvalue("display_area")) or 0.8
    protect = int((1.0 - display_area) * height)
    # from https://github.com/itKelis/MPV-Play-BiliBili-Comments
    ass = xml2ass2.xml2ass(cid,width,height,protect,font,fontsize,alpha,duration_marquee,duration_still,None,None,is_reduce_comments)

    # try:
    #     resp = requests.get("https://comment.bilibili.com/" + str(cid) +".xml", headers=headers)
    #     resp.encoding = 'utf-8'
    #     if (resp.text):
    #         width = isFloat(getvalue("width")) and int(getvalue("width")) or 1920
    #         height = isFloat(getvalue("height")) and int(getvalue("height")) or 1080
    #         font = getvalue("font") or "微软雅黑"
    #         # font = getvalue("font") or "sans-serif"
    #         fontsize = isFloat(getvalue("font_size")) and float(getvalue("font_size")) or 40.0
    #         alpha = isFloat(getvalue("alpha")) and float(getvalue("alpha")) or 0.8
    #         duration_marquee = isFloat(getvalue("duration_marquee")) and float(getvalue("duration_marquee")) or 5.0
    #         duration_still = isFloat(getvalue("duration_still")) and float(getvalue("duration_still")) or 5.0
    #         is_reduce_comments = getvalue("is_reduce_comments").upper() == "TRUE"
    #         protect = isFloat(getvalue("width")) and int(getvalue("width")) or int(height*0.2)
    #         ass = BilibiliDanmaku(resp.text,width=width,height=height,protect=protect,font=font, fontsize=fontsize, alpha=alpha,duration_marquee=duration_marquee,duration_still=duration_still,is_reduce_comments=is_reduce_comments).toAss()            

    # except Exception as e:
    #     return Response(str(e), mimetype="text/plain")

    return Response(ass, mimetype="text/plain")

def isFloat(x):
    try:
        float(x)
        return True
    except:
        return False

def getvalue(key):
    value = ""
    if request.method == 'POST':
        value = request.form.get(key, "")
    elif request.method == 'GET':
        value = request.args.get(key, "")
    return value

if __name__ == '__main__':
    app.config['JSON_AS_ASCII'] = False
    app.run(debug=True, host="0.0.0.0", port=8080)