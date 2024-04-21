import requests
import json
import os
import urllib.parse
from tqdm import tqdm
from pySmartDL import SmartDL
from functools import reduce
from hashlib import md5
import time

class Bili:
    Referer = "https://www.bilibili.com"
    UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36 Edg/90.0.818.49"
    Cookie = ""

    img_key = ""
    sub_key = ""

    @staticmethod
    def get(url):
        headers = {"Referer": Bili.Referer, "User-Agent": Bili.UserAgent, "Cookie": Bili.Cookie}
        response = requests.get(url, headers=headers, verify=False)
        return response

    @staticmethod
    def postUrlEncoded(url, data):
        headers = {"Referer": Bili.Referer, "User-Agent": Bili.UserAgent, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "Cookie": Bili.Cookie}
        response = requests.post(url, headers=headers, data=data, verify=False)
        return response

    @staticmethod
    def postJson(url, data):
        headers = {"Referer": Bili.Referer, "User-Agent": Bili.UserAgent, "Content-Type": "application/json;charset=UTF-8", "Cookie": Bili.Cookie}
        response = requests.post(url, headers=headers, data=json.dumps(data), verify=False)
        return response

    @staticmethod
    def downloadFileNew(url, file_path, progressbar, event):
        progressbar['maximum'] = 1
        headers = {"Referer": Bili.Referer, "User-Agent": Bili.UserAgent, "Content-Type": "application/json;charset=UTF-8", "Cookie": Bili.Cookie}
        obj = SmartDL(url, file_path, request_args={"headers": headers}, verify=False)
        obj.start(blocking=False)

        while not obj.isFinished():
            #print(f"Downloading: {obj.get_progress()}")
            progressbar['value'] = obj.get_progress()
            progressbar.update_idletasks()

        print("Downloaded file:", obj.get_dest())
        event.set()  # 设置事件，表示下载完成

    @staticmethod
    def downloadFile(url, backurl, file_path, progressbar, event, max_retries):
        # 设置重试次数和每次读取的字节数
        chunk_size = 1024
        backup_id = -1
        i = 0

        # 循环重试下载
        while i < max_retries:
            i += 1
            try:
                dir_path = os.path.dirname(file_path)
    
                # 如果目录不存在，则创建目录
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)

                # 如果文件已经存在，则获取已下载的字节数
                if os.path.exists(file_path):
                    downloaded_size = os.path.getsize(file_path)
                else:
                    downloaded_size = 0

                # 发送带有Range头的请求
                headers = {"Referer": Bili.Referer, "User-Agent": Bili.UserAgent, "Content-Type": "application/json;charset=UTF-8", "Cookie": Bili.Cookie, 'Range': 'bytes=%d-' % downloaded_size}

                response = requests.head(url, headers=headers, stream=True, verify=False)
                file_size = int(response.headers.get('Content-Length', 0))
                progressbar['maximum'] = file_size
                progressbar['value'] = 0
                downloaded_size = 0
                
                # 下载文件并显示进度
                with requests.get(url, headers=headers, stream=True, verify=False, timeout=10) as r, open(file_path, 'ab') as f, tqdm(
                    desc=file_path,
                    total=file_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as pbar:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))
                        # 更新进度条
                        downloaded_size += len(chunk)
                        progressbar['value'] += len(chunk)
                        progressbar.update_idletasks()
                # 下载成功，退出循环
                if downloaded_size < file_size or downloaded_size < 600:
                    print(f"第{i}次下载，{downloaded_size}/{file_size}")
                    if i == max_retries:
                        if backup_id == len(backurl) - 1:
                            with open(file_path, "w") as file:
                                file.truncate(0)
                            break
                        else:
                            backup_id = backup_id + 1
                            print(f"使用备用地址{backup_id}")
                            url = backurl[backup_id]
                            i = 0
                            continue
                    else:
                        continue
                break
            except Exception as e:
                print(f"Failed to download file: {e}")
                # 出现异常，继续下一次重试
                if i == max_retries:
                    if backup_id == len(backurl) - 1:
                        with open(file_path, "w") as file:
                            file.truncate(0)
                        break
                    else:
                        backup_id = backup_id + 1
                        print(f"使用备用地址{backup_id}")
                        url = backurl[backup_id]
                        i = 0
                        continue
                else:
                    continue

        event.set()  # 设置事件，表示下载完成
        return file_path

    @staticmethod
    def parseReply(reply, requiredKey):
        if reply.status_code != 200:
            print("network error:", reply.status_code, reply.reason, ", url=", reply.url)
            return {}, "网络请求错误"

        if "json" not in reply.headers.get("Content-Type", ""):
            return {}, "http请求错误"

        jsonObj = reply.json()
        print("reply from", reply.url)  # << QString::fromUtf8(data);

        if not jsonObj:
            return {}, "http请求错误"

        code = jsonObj.get("code", 0)
        if code < 0 or (requiredKey and Bili.isJsonValueInvalid(jsonObj.get(requiredKey))):
            if "message" in jsonObj:
                return jsonObj, jsonObj["message"]
            if "msg" in jsonObj:
                return jsonObj, jsonObj["msg"]

            format = "B站请求错误: code = %1, requiredKey = %2\nURL: %3"
            msg = format.format(str(code), requiredKey, reply.url)
            return jsonObj, msg

        return jsonObj, ""

    @staticmethod
    def isJsonValueInvalid(val):
        return val is None

    mixinKeyEncTab = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    ]

    @staticmethod
    def getMixinKey(orig: str):
        '对 imgKey 和 subKey 进行字符顺序打乱编码'
        return reduce(lambda s, i: s + orig[i], Bili.mixinKeyEncTab, '')[:32]

    @staticmethod
    def encWbi(params: dict, img_key: str, sub_key: str):
        '为请求参数进行 wbi 签名'
        mixin_key = Bili.getMixinKey(img_key + sub_key)
        curr_time = round(time.time())
        params['wts'] = curr_time                                   # 添加 wts 字段
        params = dict(sorted(params.items()))                       # 按照 key 重排参数
        # 过滤 value 中的 "!'()*" 字符
        params = {
            k : ''.join(filter(lambda chr: chr not in "!'()*", str(v)))
            for k, v 
            in params.items()
        }
        query = urllib.parse.urlencode(params)                      # 序列化参数
        wbi_sign = md5((query + mixin_key).encode()).hexdigest()    # 计算 w_rid
        params['w_rid'] = wbi_sign
        return params

    @staticmethod
    def getWbiKeys():
        '获取最新的 img_key 和 sub_key'
        reply = Bili.get("https://api.bilibili.com/x/web-interface/nav")
        json, errorString = Bili.parseReply(reply, "data")
        img_url: str = json['data']['wbi_img']['img_url']
        sub_url: str = json['data']['wbi_img']['sub_url']
        img_key = img_url.rsplit('/', 1)[1].split('.')[0]
        sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
        return img_key, sub_key

    @staticmethod
    def getQueryURL(params):
        if Bili.img_key == "":
            Bili.img_key, Bili.sub_key = Bili.getWbiKeys()

        signed_params = Bili.encWbi(
            params=params,
            img_key=Bili.img_key,
            sub_key=Bili.sub_key
        )
        query = urllib.parse.urlencode(signed_params)
        return query