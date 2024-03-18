#!/usr/bin/env python

import os
import xml.dom.minidom as xmldom
import base64
import hashlib
#import io
#from PIL import Image

def visit_all_dirs_and_files(directory, convert_list, poster, fanart):
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if '@eaDir' in root:
                continue
            _, ext = os.path.splitext(filename)
            if ext.lower() in ['.mkv', '.mp4', '.rmvb', '.avi', '.wmv', '.ts']:  #设置视频文件格式后缀，缺少的自行增加
                vsmeta_path = os.path.join(root, filename + '.vsmeta')
                #以下两行代码用于删除已有vsmeta文件
                #if os.path.exists(vsmeta_path):
                #    os.remove(vsmeta_path)
                poster_path = os.path.join(root, poster)
                fanart_path = os.path.join(root, fanart)
                if not os.path.exists(vsmeta_path):
                    nfo_path = os.path.join(root, os.path.splitext(filename)[0] + '.nfo')
                    convert_list.append(nfo_path)
                    if os.path.exists(nfo_path):
                        try:
                            action(nfo_path, vsmeta_path, poster_path, fanart_path)
                        except Exception as e:
                            print(e)
            elif ext.lower() not in ['.vsmeta', '.jpg', '.nfo', '.srt', '.ass', '.ssa', '.png', '.db']:  #用于检查缺少的视频文件格式后缀。需要忽略的文件格式后缀自行增加
                print('Unrecognized file:', os.path.join(root, filename))

def action(nfo_path, target_path, poster_path, fanart_path):
    
    doc = xmldom.parse(nfo_path)
    title = getNode(doc, 'title', '无标题')
    sorttitle = getNode(doc, 'sorttitle', title)
    plot = getNode(doc, 'plot', ' ')
    year = getNode(doc, 'year', '1900')
    level = getNode(doc, 'mpaa', 'G')
    date = getNode(doc, 'premiered', '1900-01-01')
    rate = getNode(doc, 'rating', '0')
    genre = getNodeList(doc, 'genre', [])
    act = getNodeList(doc, 'name', [])
    direc = getNodeList(doc, 'director', [])
    writ = getNodeList(doc, 'writer', [])
#    stu = getNodeList(doc, 'studio', [])


    with open(target_path, 'wb') as output:
        writeTag(output, 0x08)
        writeTag(output, 0x01)

        writeTag(output, 0x12)
        writeString(output, title)

        writeTag(output, 0x1A)
        writeString(output, title)

        writeTag(output, 0x22)
        writeString(output, sorttitle)

        writeTag(output, 0x28)
        writeTag(output, 0xDC)#待定，含义不明，不是年份
        #writeInt(output, year)
        writeTag(output, 0x0F)

        writeTag(output, 0x32)
        writeString(output, date)

        writeTag(output, 0x38)
        writeTag(output, 0x01)

        writeTag(output, 0x42)
        writeString(output, plot)

        writeTag(output, 0x4A)
        writeString(output, 'null')

        writeTag(output, 0x52)
        writeLength(output, getGroupLen(genre) + getGroupLen(act) + getGroupLen(direc) + getGroupLen(writ))

        for a in act:
            writeTag(output, 0x0A)
            writeString(output, a)

        for d in direc:
            writeTag(output, 0x12)
            writeString(output, d)

        for g in genre:
            writeTag(output, 0x1A)
            writeString(output, g)

        for w in writ:
            writeTag(output, 0x22)
            writeString(output, w)

        writeTag(output, 0x5A)
        writeString(output, level)

        writeTag(output, 0x60)
        writeInt(output, int(float(rate) * 10))

        splitleng = 76
        if os.path.exists(poster_path):
            writeTag(output, 0x8A)
            writeTag(output, 0x01)

            with open(poster_path, "rb") as p:
                poster_bytes = p.read()

#            img = Image.open(io.BytesIO(poster_bytes))
#            final_img = img.resize((472, 700), Image.LANCZOS)
#            img_byte = io.BytesIO()
#            final_img.save(img_byte, 'png')
#            posterBase64 = base64.b64encode(img_byte.getvalue()).decode('utf-8')
#            print(posterBase64)
            posterBase64 = base64.b64encode(poster_bytes).decode('utf-8')
            posterList = [posterBase64[i:i+splitleng] for i in range(0, len(posterBase64), splitleng)]
            posterFinal = '\n'.join(posterList)
            posterMd5 = hashlib.md5(posterFinal.encode("utf-8")).hexdigest()

            writeString(output, posterFinal)
            writeTag(output, 0x92)
            writeTag(output, 0x01)
            writeString(output, posterMd5)

        if os.path.exists(fanart_path):
            writeTag(output, 0xAA)
            writeTag(output, 0x01)

            with open(fanart_path, "rb") as f:
                fanart_bytes = f.read()
            fanartBase64 = base64.b64encode(fanart_bytes).decode('utf-8')
            fanartList = [fanartBase64[i:i+splitleng] for i in range(0, len(fanartBase64), splitleng)]
            fanartFinal = '\n'.join(fanartList)
            fanartMd5 = hashlib.md5(fanartFinal.encode("utf-8")).hexdigest()

            writeLength(output, lenOfEncode(fanartFinal)+40)#写两次长度，第一次含md5及所有标签的总长度，故+40
            writeTag(output, 0x0A)
            writeString(output, fanartFinal)
            writeTag(output, 0x12)
            writeString(output, fanartMd5)

        writeTag(output, 0x18)
        writeTag(output, 0xB2)#待定，含义不明
        writeTag(output, 0x9E)#待定，含义不明
        writeTag(output, 0xCC)#待定，含义不明
        writeTag(output, 0xAF)
        writeTag(output, 0x06)


def lenOfEncode(string):
    return len(string.encode('utf-8'))

def getGroupLen(l):
    if len(l) < 1 :
        return 0
    return lenOfEncode('12'.join(l)) + 2#每个人员有两位占位符，故每个元素+2的长度

def writeTag(op, t):
    op.write(bytes([int(str(t))]))

def writeInt(op, i):
    op.write(i.to_bytes(1, 'little'))

def writeString(op, string):
    writeByte(op, string.encode('utf-8'))

def writeByte(op, byte):
    length = len(byte)
    writeLength(op, length)
    op.write(byte)

def writeLength(op, len):
    while len > 128:
        op.write(bytes([len % 128 + 128]))
        len = len // 128
    op.write(bytes([len]))

def getNode(doc, tag, default):
    nd = doc.getElementsByTagName(tag)
    if len(nd) < 1 or not nd[0].hasChildNodes() :
        return default
    return nd[0].firstChild.nodeValue

def getNodeList(doc, tag, default):
    node = doc.getElementsByTagName(tag)
    if len(node) < 1 or not node[0].hasChildNodes() :
        return default
    return [nd.firstChild.nodeValue for nd in doc.getElementsByTagName(tag)]

if __name__ == '__main__':
    poster = 'poster.jpg'#封面图默认名
    fanart = 'fanart.jpg'#背景图默认名
    directory = r'/volume1/video/Links/Movie/'
    convert_list = []
    visit_all_dirs_and_files(directory, convert_list, poster, fanart)

    print('success ' + str(len(convert_list)) + ' files')
    #for item in convert_list:
    #    print(item)
