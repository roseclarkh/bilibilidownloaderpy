import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import re
from network import Bili
from urllib.parse import urlparse, parse_qs
from io import BytesIO
import threading
import datetime
import os
import subprocess
import shutil
import urllib3
import json
import sys
import webbrowser

def saveJson(path, data):
    with open(path, 'w') as file:
        json.dump(data, file)

def loadJson(path):
    if os.path.exists(path):
        with open(path, 'r', encoding="utf-8") as file:
            return json.load(file)
    return []

def loadText(path):
    if os.path.exists(path):
        with open(path, 'r') as file:
            return file.read()
    else:
        return ""

def saveText(path, text):
    with open(path, 'w') as file:
        file.write(text)

def saveCache():
    saveJson("cache.json", download_arr)

def loadCache():
    return loadJson("cache.json")

def isEmpty(file_path):
    return os.path.exists(file_path) and os.path.getsize(file_path) == 0

def on_clearall_clicked():
    global current_id
    result = messagebox.askyesno("确认", "是否清除掉队列所有数据？该操作无法撤销！")
    if result:
        download_arr.clear()
        saveCache()
        current_id = 0
        tree.delete(*tree.get_children())
        updateTable()

def on_cleardone_clicked():
    global current_id, download_arr
    result = messagebox.askyesno("确认", "是否清除掉队列已完成数据？该操作无法撤销！")
    if result and Bili.is_downloading == False:
        download_button.config(state='disabled')
        all_button.config(state='disabled')
        done_button.config(state='disabled')
        retry_input.config(state='disabled')
        stop_button.config(state='normal')
        Bili.is_downloading = True
        current_id = 0
        downloadAll(True)

def on_parse_clicked():
    global download_arr
    input_url = input_text.get()
    if input_url != "":
        #单条视频
        if "com/video/BV" in input_url:
            bvid = parse_bvid(input_url)
            bvdata = start_bvid(bvid)
            download_arr.append(bvdata)
        elif "com/x/space/wbi/arc/search?" in input_url:
            videoes, page = parse_search(input_url)
            download_arr.extend(videoes)
        elif "space.bilibili.com/" in input_url:
            if "/channel/collectiondetail" in input_url:
                parse_collection(input_url)
            else:
                parse_homepage(input_url)

        download_arr = list({item["bvid"]: item for item in download_arr}.values())
        trace("去重剩余" + str(len(download_arr)) + "条数据\n")
        saveCache()
        updateTable()

def on_download_clicked():
    global current_id, download_arr
    if Bili.is_downloading == False:
        download_button.config(state='disabled')
        all_button.config(state='disabled')
        done_button.config(state='disabled')
        clear_button.config(state='disabled')
        retry_input.config(state='disabled')
        stop_button.config(state='normal')
        Bili.is_downloading = True
        current_id = 0
        try:
            selected_row = tree.selection()[0]
            current_id = tree.index(selected_row)
        except Exception as e:
            print(f"选择行失败: {e}")
        download_arr = [{k: v for k, v in item.items() if k != "video_url" } for item in download_arr]
        downloadAll(False)

def on_stop_clicked():
    if Bili.is_downloading == True:
        download_button.config(state='normal')
        all_button.config(state='normal')
        done_button.config(state='normal')
        retry_input.config(state='normal')
        clear_button.config(state='normal')
        stop_button.config(state='disabled')
        Bili.is_downloading = False

def on_cleartemp_clicked():
    if os.path.exists("temp"):
        shutil.rmtree("temp")
        trace("缓存目录已清空\n")

def parse_bvid(url):
    url = urlparse(url)
    host = url.netloc.lower()
    path = url.path
    query = parse_qs(url.query)

    if (m := re.match(r"^/(?:(?:s/)?video/)?(?:BV|bv)([a-zA-Z0-9]+)/?$", path)):
        url = "BV" + m.group(1)
    else:
        trace(f"解析失败：{url}\n")
        return ""

    trace(f"解析结果：{url}\n")
    return url

def start_bvid(bvid):
    reply = Bili.get("https://api.bilibili.com/x/web-interface/view?bvid=" + bvid)
    json, errorString = Bili.parseReply(reply, "data")
    
    if "data" in json:
        data = json["data"]
    else:
        data = ""

    trace(f"解析bvid：{bvid}\n")

    return data

def parse_search(url):
    reply = Bili.get(url)
    json, errorString = Bili.parseReply(reply, "data")
    #trace(reply);
    data = json["data"]["list"]["vlist"]
    page = json["data"]["page"]
    length = len(data)
    trace(f"解析结果：{length}条\n")

    return data, page

def parse_archives(url):
    reply = Bili.get(url)
    json, errorString = Bili.parseReply(reply, "data")
    #trace(reply);
    data = json["data"]["archives"]
    page = json["data"]["page"]
    meta = json["data"]["meta"]
    length = len(data)
    trace(f"解析结果：{length}条\n")

    return data, page, meta

def parse_collection(url):
    #https://space.bilibili.com/43707221/channel/collectiondetail?sid=1018407
    url_parts = url.split('?')  # 将URL按照?进行切割，得到["https://space.bilibili.com/482500145", "spm_id_from=333.337.0.0"]
    if len(url_parts) > 1:
        match = re.search(r'\d+', url_parts[0])  # 在切割后的第一部分中匹配数字
        if match:
            mid = match.group()  # 提取匹配到的数字
            match = re.search(r'\bsid=(\d+)', url_parts[1])
            if match:
                videos = []
                sid = match.group(1)
                print(mid, sid)
                videos = []
                parse_mid_collection(mid, sid, videos)
                for bvdata in videos:
                    if "author" in bvdata and "is_union_video" in bvdata and bvdata["is_union_video"] == 0:
                        author_name = bvdata["author"]
                download_arr.extend(videos)


def parse_homepage(url):
    url_parts = url.split('?')  # 将URL按照?进行切割，得到["https://space.bilibili.com/482500145", "spm_id_from=333.337.0.0"]
    if len(url_parts) > 0:
        match = re.search(r'\d+', url_parts[0])  # 在切割后的第一部分中匹配数字
        if match:
            mid = match.group()  # 提取匹配到的数字
            videos = []
            parse_mid(mid, videos)
            author_name = ""
            if author_name != "":
                for bvdata in videos:
                    bvdata["author_name"] = author_name
            download_arr.extend(videos)

def parse_mid_collection(mid, sid, videos, pn = 1, ps = 50):
    params = {
        "mid": mid,
        "season_id": sid,
        "sort_reverse": "true",
        "page_size": ps,
        "page_num": pn
    }
    trace(f"解析第{pn}页...")
    url = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?" + Bili.getQueryURL(params)
    datas, page, meta = parse_archives(url)
    for bvdata in datas:
        bvdata["author"] = meta["name"]
        bvdata["pubdate"] = meta["ptime"]
        bvdata["mid"] = meta["mid"]
    videos.extend(datas)
    if page["page_size"] * page["page_num"] <  page["total"]:
        parse_mid_collection(mid, sid, videos, pn + 1, ps)

def parse_mid(mid, videos, pn = 1, ps = 50):
    params = {
        "mid": mid,
        "ps": ps,
        "pn": pn,
        "order": "pubdate",
        "platform": "web"
    }
    trace(f"解析第{pn}页...")
    url = "https://api.bilibili.com/x/space/wbi/arc/search?" + Bili.getQueryURL(params)
    datas, page = parse_search(url)
    videos.extend(datas)
    if page["pn"] * page["ps"] <  page["count"]:
        parse_mid(mid, videos, pn + 1, ps)

def downloadAll(onlyCheck):
    global current_id, download_arr

    queuebar["value"] = current_id
    queuebar["maximum"] = len(download_arr)
    queuebar.update_idletasks()
        
    updateTable()

    if Bili.is_downloading == False:
        if onlyCheck == True:
            trace("检查已停止")
            download_arr = [item for item in download_arr if item.get("status") != "已完成"]
            saveCache()
            current_id = 0
            tree.delete(*tree.get_children())
            updateTable()
        else:
            trace("下载已停止")
        return

    if current_id >= len(download_arr):
        on_stop_clicked()
        if onlyCheck == True:
            trace("检查已完成")
            download_arr = [item for item in download_arr if item.get("status") != "已完成"]
            saveCache()
            current_id = 0
            tree.delete(*tree.get_children())
            updateTable()
        else:
            trace("下载已完成")
        return

    bvdata = download_arr[current_id]

    # 未解析地址
    if not "download_file" in bvdata:
        bvdata["status"] = "解析下载"
        parsePlayUrl(bvdata, False, onlyCheck)
        root.after(1, downloadAll, onlyCheck)
    # 文件已下载
    elif os.path.exists(bvdata["download_file"]):
        trace("文件已存在：" + bvdata["download_file"] + "\n")
        #for staff_file in bvdata["staff_file"]:
            #if os.path.exists(staff_file):
                #trace("文件已存在：" + staff_file + "\n")
            #else:
                #shutil.copy(bvdata["download_file"], staff_file)
                #trace("文件已复制：" + staff_file + "\n")
        bvdata["status"] = "已完成"
        current_id += 1
        root.after(1, downloadAll, onlyCheck)
    # 只检查状态
    elif onlyCheck == True:
        current_id = current_id + 1
        root.after(1, downloadAll, onlyCheck)
    # 未解析cid
    elif not "cid" in bvdata:
        bvdata["status"] = "解析数据"
        parseData = start_bvid(bvdata["bvid"])

        if parseData == "":
            current_id = current_id + 1
            bvdata["status"] = "解析失败"
        else:
            download_arr[current_id] = {**bvdata, **parseData}

        root.after(1, downloadAll, onlyCheck)
    # 未解析地址
    elif not "video_url" in bvdata:
        bvdata["status"] = "解析视频"
        parsePlayUrl(bvdata, True, onlyCheck)
        root.after(1, downloadAll, onlyCheck)
    elif not os.path.exists(bvdata["temp_file"]):
        bvdata["status"] = "下载视频"
        updateTable()
        downloadVideo(bvdata)
    elif isEmpty(bvdata["temp_file"]):
        bvdata["status"] = "视频失败"
        current_id = current_id + 1
        root.after(1, downloadAll, onlyCheck)
    elif not os.path.exists(bvdata["temp_file"] + ".m4a"):
        bvdata["status"] = "下载音频"
        updateTable()
        downloadAudio(bvdata)
    elif isEmpty(bvdata["temp_file"] + ".m4a"):
        bvdata["status"] = "音频失败"
        current_id = current_id + 1
        root.after(1, downloadAll, onlyCheck)
    else:
        bvdata["status"] = "开始合成"
        updateTable()
        joinVideo(bvdata)

def parsePlayUrl(bvdata, parse = False, onlyCheck = False):
    global current_id
    aid = bvdata["aid"]
    qn = 120
    if "created" in bvdata:
        timestamp = bvdata["created"]
    elif "pubdate" in bvdata:
        timestamp = bvdata["pubdate"]
    else:
        timestamp = 0
    title = bvdata["title"]
    date = datetime.datetime.utcfromtimestamp(timestamp)
    formatted_date = date.strftime("%Y%m%d_%H%M%S")
    if "author_name" in bvdata:
        owner = bvdata["author_name"]
    elif "author" in bvdata:
        owner = bvdata["author"]
    else:
        owner = bvdata["owner"]["name"]
    temp_dir = os.path.join("temp", replace_invalid_filename_chars(owner))
    download_dir = os.path.join("download", replace_invalid_filename_chars(owner))
    file_name = replace_invalid_filename_chars(formatted_date + "_" + title + ".mp4")

    # 确保下载目录存在
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(download_dir, exist_ok=True)

    bvdata["temp_file"] = os.path.join(temp_dir, file_name)
    bvdata["download_file"] = os.path.join(download_dir, file_name)
    bvdata["staff_file"] = []

    # 共创
    if "staff" in bvdata:
        for staff in bvdata["staff"]:
            if staff["name"] != owner:
                staff_dir = os.path.join("download", replace_invalid_filename_chars(staff["name"]))
                staff_file = os.path.join(staff_dir, file_name)
                # os.makedirs(staff_dir, exist_ok=True)
                bvdata["staff_file"].append(staff_file)

    #trace(bvdata["download_file"] + "," + str(parse))

    if parse == False:
        return
    
    cid = bvdata["cid"]

    trace(f"解析目标文件[" + str(parse) + "]：" + bvdata["download_file"] + "\n")

    api = "https://api.bilibili.com/x/player/wbi/playurl"
    query = f"?avid={aid}&cid={cid}&qn={qn}&fourk=1&fnval=4048"
    reply = Bili.get(api + query)
    json, errorString = Bili.parseReply(reply, "data")

    if "data" in json:
        data = json["data"]

        video_w = 0
        video_h = 0

        if "dash" in data:
            video = data["dash"]["video"][0]
            video_w = video["width"]
            video_h = video["height"]
            bvdata["video_url"] = video["baseUrl"]
            if "backupUrl" in video:
                bvdata["backup_video"] = video["backupUrl"]
            else:
                bvdata["backup_video"] = []
            audio = data["dash"]["audio"][0]
            bvdata["audio_url"] = audio["baseUrl"]
            if "backupUrl" in audio:
                bvdata["backup_audio"] = audio["backupUrl"]
            else:
                bvdata["backup_audio"] = []
        elif "durl" in data:
            video = data["durl"][0]
            bvdata["video_url"] = video["url"]
            if "backup_url" in video:
                bvdata["backup_video"] = video["backup_url"]
            else:
                bvdata["backup_video"] = []

        bvdata["video_w"] = video_w
        bvdata["video_h"] = video_h

        trace(f"解析下载地址：{video_w}x{video_h} {owner} {file_name}\n")
    else:
        if errorString == "87008":
            bvdata["status"] = "充电专属"
        else:
            bvdata["status"] = "解析错误"
        trace("解析错误" + errorString + "\n")
        current_id = current_id + 1

    saveCache()

def downloadVideo(bvdata):
    if not "audio_url" in bvdata:
        save_path = bvdata["download_file"]
    else:
        save_path = bvdata["temp_file"]
    # 拼接保存路径
    download_complete_event = threading.Event()  # 创建事件
    job = threading.Thread(target=Bili.downloadFile, args=(bvdata["video_url"], bvdata["backup_video"], save_path, progressbar, download_complete_event, int(retry_input.get())))
    job.start()
    root.after(100, check_download_complete, download_complete_event)
    trace("下载视频...")

def downloadAudio(bvdata):
    # 拼接保存路径
    download_complete_event = threading.Event()  # 创建事件
    job = threading.Thread(target=Bili.downloadFile, args=(bvdata["audio_url"], bvdata["backup_audio"], bvdata["temp_file"] + ".m4a", progressbar, download_complete_event, int(retry_input.get())))
    job.start()
    root.after(100, check_download_complete, download_complete_event)
    trace(f"下载音频...")

def joinVideo(bvdata):
    trace(f"开始合成...")    
    ffmpeg_cmd = ['ffmpeg.exe', '-i', bvdata["temp_file"], '-i', bvdata["temp_file"] + ".m4a", '-c:v', 'copy', '-c:a', 'copy', bvdata["download_file"]]
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # 等待子进程执行完毕
    stdout, stderr = process.communicate()
    # 在这里可以进行一些操作，比如输出子进程的输出
    trace(f"合成完毕\n")
    os.remove(bvdata["temp_file"])
    os.remove(bvdata["temp_file"] + ".m4a")
    downloadAll(False)

def check_download_complete(event):
    if Bili.is_downloading == False:
        trace(f"下载已停止。")
        return

    if event.is_set():
        trace(f"下载完成。")
        downloadAll(False)
    else:
        root.after(100, check_download_complete, event)

def replace_invalid_filename_chars(filename):
    # 定义非法字符的正则表达式
    invalid_chars = '[\r\n<>:"/\\|?*]'
    # 将非法字符替换为下划线
    return re.sub(invalid_chars, '_', filename)

def trace(txt):
    output_text.insert(tk.END, txt)
    output_text.yview_moveto(1.0)

def updateTable():
    row_count = len(tree.get_children())
    for i in range(0, len(download_arr)):
        bvdata = download_arr[i]
        if "created" in bvdata:
            timestamp = bvdata["created"]
        elif "pubdate" in bvdata:
            timestamp = bvdata["pubdate"]
        else:
            timestamp = 0
        title = bvdata["title"]
        date = datetime.datetime.utcfromtimestamp(timestamp)
        formatted_date = date.strftime("%Y-%m-%d %H:%M:%S")
        if "author_name" in bvdata:
            owner = bvdata["author_name"]
        elif "author" in bvdata:
            owner = bvdata["author"]
        elif "owner" in bvdata:
            owner = bvdata["owner"]["name"]
        else:
            owner = "未知"
        if "staff" in bvdata:
            for staff in bvdata["staff"]:
                if staff["name"] != owner:
                    owner = owner + "," + staff["name"]

        if "video_w" in bvdata:
            size = f"{bvdata['video_w']}x{bvdata['video_h']}"
        else:
            size = ""

        if "status" in bvdata:
            status = bvdata["status"]
        else:
            status = ""

        formatted_date = date.strftime("%Y%m%d_%H%M%S")
        download_dir = os.path.join("download", replace_invalid_filename_chars(owner))
        file_name = replace_invalid_filename_chars(formatted_date + "_" + title + ".mp4")

        if i >= row_count:
            row_count  = row_count + 1
            tree.insert('', i, text=(i + 1), values=(title, owner, formatted_date, size, file_name, status, bvdata["bvid"]))
        elif i <= current_id:
            item_id = tree.get_children()[i]
            tree.item(item_id, values=(title, owner, formatted_date, size, file_name, status, bvdata["bvid"]))
        
    if row_count > 0 and current_id < row_count - 1:
        line = tree.get_children()[current_id]
        tree.selection_set(line)
        tree.focus(line)
        tree.see(line)

def onTableClicked(event):
    region = tree.identify_region(event.x, event.y)
    if region == "cell":
        col_id = tree.identify_column(event.x)
        row_id = tree.identify_row(event.y)
        values = tree.item(row_id, "values")
        index = tree.index(row_id)
        if values:
            download_dir = os.path.join("download", replace_invalid_filename_chars(values[1]))
            file_name = os.path.join(download_dir, replace_invalid_filename_chars(values[4]))

            if col_id == "#2":
                if os.path.exists(file_name):
                    subprocess.Popen(['explorer', '/select,', file_name], shell=True)
                else:
                    subprocess.Popen(['explorer', '/open,', download_dir], shell=True)
            elif col_id != "#1" and os.path.exists(file_name):
                    saveText("tmp.bat", '"' + file_name + '"')
                    subprocess.Popen(["tmp.bat"], shell=True)
            else:
                webbrowser.open("https://www.bilibili.com/video/" + values[6])

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.setrecursionlimit(10000)  # 设置递归深度限制为3000或更高

script_dir = os.path.dirname(os.path.abspath(__file__))

os.chdir(script_dir)

download_arr = []
current_id = 0

root = tk.Tk()
root.title("对话框")
root.geometry("800x600")

#login_button = tk.Button(root, text="登录", command=on_login_clicked)
# 创建两个容器来分组
groupline = tk.Frame(root)

if os.path.exists("history.txt"):
    history_arr = loadJson("history.txt")

input_text = ttk.Combobox(groupline, values=history_arr)
parse_button = tk.Button(groupline, text="解析网址", command=on_parse_clicked)
input_text.grid(row=0, column=0, padx=5, sticky="nsew")
parse_button.grid(row=0, column=1, padx=5)

groupline.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
groupline.grid_columnconfigure(0, weight=1)

groupline = tk.Frame(root)

download_button = tk.Button(groupline, text="开始下载", command=on_download_clicked)
stop_button = tk.Button(groupline, text="停止下载", command=on_stop_clicked)
#retry_status = tk.IntVar()
#retry_checkbox = tk.Checkbutton(groupline, text="允许重试", variable=retry_status)
retry_label = tk.Label(groupline, text="下载重试次数")

def validate_input(new_value):
    if len(new_value) <= 6 and new_value.isdigit():
        return True
    return False

stop_button.config(state='disabled')

validation = groupline.register(validate_input)
retry_input = tk.Entry(groupline, width=6, validate="key", validatecommand=(validation, '%P'))

download_button.grid(row=0, column=0, padx=5)
stop_button.grid(row=0, column=1, padx=5, sticky="w")
retry_label.grid(row=0, column=2, padx=5, sticky="w")
retry_input.grid(row=0, column=3, padx=5, sticky="w")
#retry_checkbox.grid(row=0, column=4, padx=5)

placeholder_label = tk.Label(groupline, text="")
placeholder_label.grid(row=0, column=4)

all_button = tk.Button(groupline, text="清除列表", command=on_clearall_clicked)
done_button = tk.Button(groupline, text="清除完成", command=on_cleardone_clicked)
clear_button = tk.Button(groupline, text="清除缓存", command=on_cleartemp_clicked)
all_button.grid(row=0, column=5, padx=5, sticky="e")
done_button.grid(row=0, column=6, padx=5, sticky="e")
clear_button.grid(row=0, column=7, padx=5, sticky="e")

groupline.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
groupline.grid_columnconfigure(4, weight=1)

groupline = tk.Frame(root)

# 创建一个Treeview
tree = ttk.Treeview(groupline, columns=('name', 'author', 'createtime', 'video', 'audio', 'status'), show="headings tree")

# 设置列的标题
tree.heading('name', text='标题')
tree.heading('author', text='作者')
tree.heading('createtime', text='时间')
tree.heading('video', text='视频')
tree.heading('audio', text='文件')
tree.heading('status', text='状态')

for col in tree["columns"]:
    tree.column(col, width=2)

tree.column("#0", width=5)
tree.column("name", width=200)
tree.column("createtime", width=50)
tree.column("video", width=30)
tree.column("audio", width=30)

# 将Treeview放置在窗口中
tree.grid(row=0, column=0, padx=5, sticky="nsew")

# 双击事件绑定
tree.bind("<Double-1>", onTableClicked)

# Create a Scrollbar and link it to the Treeview
scrollbar = ttk.Scrollbar(groupline, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=scrollbar.set)
scrollbar.grid(row=0, column=1, sticky="ns")

groupline.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")
groupline.grid_rowconfigure(0, weight=1)
groupline.grid_columnconfigure(0, weight=1)

groupline = tk.Frame(root)

output_text = tk.Text(groupline, height=10, width=40, wrap=tk.WORD)
progressbar = ttk.Progressbar(groupline, orient='horizontal', length=200, mode='determinate')
queuebar = ttk.Progressbar(groupline, orient='horizontal', length=200, mode='determinate')

output_text.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
queuebar.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
progressbar.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

groupline.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
groupline.grid_columnconfigure(0, weight=1)

root.grid_rowconfigure(2, weight=1)
root.grid_columnconfigure(0, weight=1)

retry_input.insert(0, "3")

#input_text.insert(0, "https://www.bilibili.com/video/BV1Xy421B71G/?spm_id_from=333.999.0.0")
#input_text.insert(0, "https://space.bilibili.com/482500145?spm_id_from=333.337.0.0")
#input_text.insert(0, "https://api.bilibili.com/x/space/wbi/arc/search?mid=1353897724&ps=30&tid=0&pn=2&keyword=&order=pubdate&platform=web&web_location=1550101&order_avoided=true&dm_img_list=[%7B%22x%22:5434,%22y%22:54,%22z%22:0,%22timestamp%22:867080,%22k%22:73,%22type%22:0%7D,%7B%22x%22:5665,%22y%22:249,%22z%22:17,%22timestamp%22:867181,%22k%22:126,%22type%22:0%7D,%7B%22x%22:5748,%22y%22:663,%22z%22:4,%22timestamp%22:868126,%22k%22:112,%22type%22:0%7D,%7B%22x%22:5814,%22y%22:707,%22z%22:136,%22timestamp%22:868238,%22k%22:97,%22type%22:0%7D,%7B%22x%22:5954,%22y%22:788,%22z%22:269,%22timestamp%22:868348,%22k%22:105,%22type%22:0%7D,%7B%22x%22:5987,%22y%22:815,%22z%22:297,%22timestamp%22:868449,%22k%22:90,%22type%22:0%7D,%7B%22x%22:5644,%22y%22:572,%22z%22:206,%22timestamp%22:868549,%22k%22:113,%22type%22:0%7D,%7B%22x%22:4932,%22y%22:-115,%22z%22:132,%22timestamp%22:868649,%22k%22:119,%22type%22:0%7D,%7B%22x%22:5362,%22y%22:286,%22z%22:764,%22timestamp%22:868750,%22k%22:89,%22type%22:0%7D,%7B%22x%22:4734,%22y%22:-436,%22z%22:303,%22timestamp%22:868850,%22k%22:94,%22type%22:0%7D,%7B%22x%22:4469,%22y%22:-757,%22z%22:160,%22timestamp%22:868951,%22k%22:112,%22type%22:0%7D,%7B%22x%22:4195,%22y%22:-1078,%22z%22:27,%22timestamp%22:869052,%22k%22:82,%22type%22:0%7D,%7B%22x%22:5425,%22y%22:151,%22z%22:1329,%22timestamp%22:869156,%22k%22:99,%22type%22:0%7D,%7B%22x%22:4438,%22y%22:-837,%22z%22:345,%22timestamp%22:869866,%22k%22:80,%22type%22:0%7D,%7B%22x%22:4933,%22y%22:-319,%22z%22:840,%22timestamp%22:869966,%22k%22:121,%22type%22:0%7D,%7B%22x%22:4618,%22y%22:-543,%22z%22:505,%22timestamp%22:870067,%22k%22:71,%22type%22:0%7D,%7B%22x%22:5848,%22y%22:715,%22z%22:1720,%22timestamp%22:870168,%22k%22:123,%22type%22:0%7D,%7B%22x%22:5848,%22y%22:733,%22z%22:1712,%22timestamp%22:870281,%22k%22:83,%22type%22:0%7D,%7B%22x%22:4762,%22y%22:-346,%22z%22:628,%22timestamp%22:872943,%22k%22:80,%22type%22:0%7D,%7B%22x%22:5389,%22y%22:282,%22z%22:1252,%22timestamp%22:874868,%22k%22:73,%22type%22:0%7D,%7B%22x%22:5757,%22y%22:993,%22z%22:913,%22timestamp%22:874968,%22k%22:112,%22type%22:0%7D,%7B%22x%22:6613,%22y%22:2036,%22z%22:1093,%22timestamp%22:875072,%22k%22:115,%22type%22:0%7D,%7B%22x%22:6601,%22y%22:6373,%22z%22:2271,%22timestamp%22:875847,%22k%22:96,%22type%22:0%7D,%7B%22x%22:4747,%22y%22:4790,%22z%22:1329,%22timestamp%22:875947,%22k%22:66,%22type%22:0%7D,%7B%22x%22:3330,%22y%22:3358,%22z%22:1337,%22timestamp%22:876049,%22k%22:120,%22type%22:0%7D,%7B%22x%22:1515,%22y%22:1399,%22z%22:506,%22timestamp%22:876150,%22k%22:78,%22type%22:0%7D,%7B%22x%22:4849,%22y%22:5371,%22z%22:2869,%22timestamp%22:876251,%22k%22:101,%22type%22:0%7D,%7B%22x%22:3143,%22y%22:3820,%22z%22:1112,%22timestamp%22:876360,%22k%22:112,%22type%22:0%7D,%7B%22x%22:7560,%22y%22:5741,%22z%22:2736,%22timestamp%22:9752260,%22k%22:86,%22type%22:0%7D,%7B%22x%22:6710,%22y%22:4869,%22z%22:1906,%22timestamp%22:9752370,%22k%22:104,%22type%22:0%7D,%7B%22x%22:5813,%22y%22:3991,%22z%22:998,%22timestamp%22:9752470,%22k%22:90,%22type%22:0%7D,%7B%22x%22:7972,%22y%22:5791,%22z%22:3176,%22timestamp%22:9752570,%22k%22:81,%22type%22:0%7D,%7B%22x%22:7556,%22y%22:5069,%22z%22:2735,%22timestamp%22:9752671,%22k%22:74,%22type%22:0%7D,%7B%22x%22:7956,%22y%22:5229,%22z%22:3096,%22timestamp%22:9752772,%22k%22:69,%22type%22:0%7D,%7B%22x%22:5943,%22y%22:3174,%22z%22:1071,%22timestamp%22:9752887,%22k%22:94,%22type%22:0%7D,%7B%22x%22:5805,%22y%22:3038,%22z%22:927,%22timestamp%22:9753017,%22k%22:82,%22type%22:0%7D,%7B%22x%22:6076,%22y%22:3253,%22z%22:1136,%22timestamp%22:9753118,%22k%22:122,%22type%22:0%7D,%7B%22x%22:6081,%22y%22:2575,%22z%22:1028,%22timestamp%22:9753218,%22k%22:92,%22type%22:0%7D,%7B%22x%22:6747,%22y%22:1894,%22z%22:2147,%22timestamp%22:9753318,%22k%22:94,%22type%22:0%7D,%7B%22x%22:5625,%22y%22:396,%22z%22:1555,%22timestamp%22:9753419,%22k%22:96,%22type%22:0%7D,%7B%22x%22:6682,%22y%22:1311,%22z%22:2900,%22timestamp%22:9753519,%22k%22:83,%22type%22:0%7D,%7B%22x%22:7006,%22y%22:1529,%22z%22:3450,%22timestamp%22:9753619,%22k%22:117,%22type%22:0%7D,%7B%22x%22:3782,%22y%22:-1764,%22z%22:364,%22timestamp%22:9753720,%22k%22:123,%22type%22:0%7D,%7B%22x%22:3888,%22y%22:-1702,%22z%22:510,%22timestamp%22:9753820,%22k%22:98,%22type%22:0%7D,%7B%22x%22:5995,%22y%22:374,%22z%22:2618,%22timestamp%22:9753920,%22k%22:89,%22type%22:0%7D,%7B%22x%22:7620,%22y%22:1962,%22z%22:4170,%22timestamp%22:9754020,%22k%22:113,%22type%22:0%7D,%7B%22x%22:6218,%22y%22:595,%22z%22:2732,%22timestamp%22:9754120,%22k%22:85,%22type%22:0%7D,%7B%22x%22:8277,%22y%22:2681,%22z%22:4779,%22timestamp%22:9754220,%22k%22:70,%22type%22:0%7D,%7B%22x%22:4196,%22y%22:-1391,%22z%22:694,%22timestamp%22:9754325,%22k%22:120,%22type%22:0%7D,%7B%22x%22:6129,%22y%22:542,%22z%22:2627,%22timestamp%22:9754463,%22k%22:94,%22type%22:0%7D]&dm_img_str=V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ&dm_cover_img_str=QU5HTEUgKEFNRCwgQU1EIFJhZGVvbihUTSkgR3JhcGhpY3MgKDB4MDAwMDE2ODEpIERpcmVjdDNEMTEgdnNfNV8wIHBzXzVfMCwgRDNEMTEpR29vZ2xlIEluYy4gKEFNRC&dm_img_inter=%7B%22ds%22:[%7B%22t%22:10,%22c%22:%22YmUtcGFnZXItaXRlbQ%22,%22p%22:[2996,64,2952],%22s%22:[392,589,780]%7D],%22wh%22:[4761,4372,77],%22of%22:[2595,3728,402]%7D&w_rid=c1a5b71ddbfbc6ad2a131f1e3e15dead&wts=1713573777")

on_cleartemp_clicked()

Bili.Cookie = loadText("cookie.txt")

download_arr = loadCache()
trace("队列已恢复" + str(len(download_arr)) + "条数据\n")
download_arr = list({item["bvid"]: item for item in download_arr}.values())
trace("去重剩余" + str(len(download_arr)) + "条数据\n")
updateTable()

root.mainloop()
