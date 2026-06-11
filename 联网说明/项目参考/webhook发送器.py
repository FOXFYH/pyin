import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import pyperclip
import time
import threading
from pathlib import Path

# ===================== 【配置区 - 与原版完全一致】 =====================
# 标准模板
STANDARD_TEMPLATE = {"Context": {"argv": {"message": "20260316213121哈哈", "test": "3"}}}

# 云函数地址列表
API_URL_LIST = {
    "免令牌": "https://1408347752-dxgsap4qrj.ap-guangzhou.tencentscf.com",
    "cf": "https://falling-sunset-a039.283731596.workers.dev/",
    "地址3": "https://foxf.eu.cc/",
    "地址4": "https://999.foxf.eu.cc/",
    "地址5": ""
}

# 金山文档 Webhook 地址列表
WEBHOOK_URL_LIST = {
    "AA50剪贴": "https://www.kdocs.cn/api/v3/ide/file/376210036343/script/V2-7EJdrSKR4XINDLqgdqxyyR/sync_task",
    "aa52网站": "https://www.kdocs.cn/api/v3/ide/file/376210036343/script/V2-3osQtePtkJl2KZ1kEUheuf/sync_task",
    "AA51测试": "https://www.kdocs.cn/api/v3/ide/file/376210036343/script/V2-7gjfNFrMGHyN1j7kRfKpvV/sync_task",
    "地址4": "",
    "地址5": "",
    "B2": "https://www.kdocs.cn/api/v3/ide/file/cgB1g30d49xW/script/V2-350tGnoIv3cFg8GvJrrg7x/sync_task"
}

# 配置保存路径
CONFIG_PATH = Path(__file__).parent / "webhook_config.json"

# ===================== 【主程序类】 =====================
class WebhookSender:
    def __init__(self, root):
        self.root = root
        self.root.title("Webhook 消息发送工具")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        # 发送模式：direct=直接发送(免云函数)  proxy=云函数中转
        self.send_mode = tk.StringVar(value="proxy")

        # 重试设置
        self.retry_enabled = tk.BooleanVar(value=True)
        self.retry_count = tk.IntVar(value=5)
        self.retry_interval = tk.IntVar(value=2)

        # 发送状态控制
        self.stop_flag = False
        self.is_sending = False

        # 加载配置
        self.config = self.load_config()
        self.create_widgets()
        self.load_ui_config()

    # ===================== 界面创建 =====================
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        ttk.Label(main_frame, text="发送模式：", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=8)
        mode_frame = ttk.Frame(main_frame)
        mode_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=8)
        ttk.Radiobutton(mode_frame, text="云函数中转（默认）", variable=self.send_mode, value="proxy", command=self.switch_mode).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="直接发送", variable=self.send_mode, value="direct", command=self.switch_mode).pack(side=tk.LEFT, padx=5)

        row += 1
        ttk.Label(main_frame, text="AirScript Token：", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=8)
        self.token_entry = ttk.Entry(main_frame, width=40)
        self.token_entry.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=8)

        row += 1
        ttk.Label(main_frame, text="云函数地址：", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=8)
        self.api_entry = ttk.Entry(main_frame, width=45)
        self.api_entry.grid(row=row, column=1, sticky=tk.W, pady=8)
        self.api_combo = ttk.Combobox(main_frame, values=list(API_URL_LIST.keys()), width=12)
        self.api_combo.grid(row=row, column=2, sticky=tk.W, pady=8, padx=5)
        self.api_combo.bind("<<ComboboxSelected>>", self.switch_api_url)

        row += 1
        ttk.Label(main_frame, text="金山文档 Webhook：", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=8)
        self.webhook_entry = ttk.Entry(main_frame, width=45)
        self.webhook_entry.grid(row=row, column=1, sticky=tk.W, pady=8)
        self.webhook_combo = ttk.Combobox(main_frame, values=list(WEBHOOK_URL_LIST.keys()), width=12)
        self.webhook_combo.grid(row=row, column=2, sticky=tk.W, pady=8, padx=5)
        self.webhook_combo.bind("<<ComboboxSelected>>", self.switch_webhook_url)

        row += 1
        ttk.Label(main_frame, text="消息内容（JSON）：", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.NW, pady=8)
        self.msg_text = scrolledtext.ScrolledText(main_frame, width=60, height=8, font=("Arial", 10))
        self.msg_text.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=8)

        row += 1
        retry_frame = ttk.LabelFrame(main_frame, text="请求重试设置", padding=10)
        retry_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=10)
        ttk.Checkbutton(retry_frame, text="启用重试", variable=self.retry_enabled).pack(side=tk.LEFT, padx=10)
        ttk.Label(retry_frame, text="重试次数:").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(retry_frame, from_=1, to=10, width=5, textvariable=self.retry_count).pack(side=tk.LEFT, padx=2)
        ttk.Label(retry_frame, text="间隔(秒):").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(retry_frame, from_=1, to=10, width=5, textvariable=self.retry_interval).pack(side=tk.LEFT, padx=2)

        row += 1
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=row, column=0, columnspan=3, pady=15)
        ttk.Button(action_frame, text="插入标准模板", command=self.insert_template, width=15).pack(side=tk.LEFT, padx=5)
        self.send_btn = ttk.Button(action_frame, text="发送消息", command=self.send_message, width=15)
        self.send_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(action_frame, text="终止发送", command=self.stop_send, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="保存配置", command=self.save_config, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="编辑地址", command=self.open_address_editor, width=15).pack(side=tk.LEFT, padx=5)

        row += 1
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=row, column=0, columnspan=3, pady=10, sticky=tk.NSEW)
        main_frame.rowconfigure(row, weight=1)
        main_frame.columnconfigure(1, weight=1)

        ttk.Label(log_frame, text="📤 发送数据", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Label(log_frame, text="� 返回数据", font=("Arial", 9, "bold")).grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        self.send_log = scrolledtext.ScrolledText(log_frame, width=40, height=10, font=("Arial", 9))
        self.send_log.grid(row=1, column=0, padx=(0, 10), pady=5, sticky=tk.NSEW)
        self.resp_log = scrolledtext.ScrolledText(log_frame, width=40, height=10, font=("Arial", 9))
        self.resp_log.grid(row=1, column=1, padx=(10, 0), pady=5, sticky=tk.NSEW)

        btn_frame = ttk.Frame(log_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=5)
        ttk.Button(btn_frame, text="复制发送数据", command=lambda: self.copy_log("send"), width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="复制返回数据", command=lambda: self.copy_log("resp"), width=15).pack(side=tk.LEFT, padx=5)

        self.switch_mode()

    # ===================== 核心功能 =====================
    def switch_mode(self):
        """切换发送模式，禁用/启用云函数输入框"""
        if self.send_mode.get() == "direct":
            self.api_entry.config(state=tk.DISABLED)
            self.api_combo.config(state=tk.DISABLED)
        else:
            self.api_entry.config(state=tk.NORMAL)
            self.api_combo.config(state=tk.NORMAL)

    def switch_api_url(self, event):
        """切换云函数快捷地址"""
        key = self.api_combo.get()
        self.api_entry.delete(0, tk.END)
        self.api_entry.insert(0, API_URL_LIST.get(key, ""))
        self.save_config()

    def switch_webhook_url(self, event):
        """切换金山Webhook快捷地址"""
        key = self.webhook_combo.get()
        self.webhook_entry.delete(0, tk.END)
        self.webhook_entry.insert(0, WEBHOOK_URL_LIST.get(key, ""))
        self.save_config()

    def insert_template(self):
        """插入标准模板"""
        self.msg_text.delete(1.0, tk.END)
        self.msg_text.insert(1.0, json.dumps(STANDARD_TEMPLATE, ensure_ascii=False, indent=2))
        self.save_config()

    def copy_log(self, log_type):
        """复制日志内容"""
        content = self.send_log.get(1.0, tk.END) if log_type == "send" else self.resp_log.get(1.0, tk.END)
        pyperclip.copy(content.strip())
        messagebox.showinfo("成功", "复制完成！")

    def open_address_editor(self):
        """打开地址编辑窗口"""
        editor = AddressEditor(self.root, self)

    def stop_send(self):
        """停止发送"""
        self.stop_flag = True

    # ===================== 核心功能 =====================
    def send_message(self):
        """发送消息（双模式适配）"""
        if self.is_sending:
            return

        self.is_sending = True
        self.stop_flag = False
        self.send_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)

        threading.Thread(target=self._send_request, daemon=True).start()

    def _send_request(self):
        """在新线程中执行请求"""
        mode = self.send_mode.get()
        api_url = self.api_entry.get().strip()
        webhook_url = self.webhook_entry.get().strip()
        msg_content = self.msg_text.get(1.0, tk.END).strip()

        self.send_log.delete(1.0, tk.END)
        self.resp_log.delete(1.0, tk.END)

        if not webhook_url:
            self.resp_log.insert(1.0, "错误：金山文档Webhook地址不能为空")
            self._send_finished()
            return
        if mode == "proxy" and not api_url:
            self.resp_log.insert(1.0, "错误：云函数地址不能为空")
            self._send_finished()
            return

        try:
            msg_json = json.loads(msg_content)
        except Exception as e:
            self.send_log.insert(1.0, f"JSON格式错误：\n{str(e)}")
            self._send_finished()
            return

        if mode == "direct":
            send_data = msg_json
            target_url = webhook_url
            self.send_log.insert(1.0, f"【直接发送模式】\n\n{json.dumps(send_data, ensure_ascii=False, indent=2)}")
        else:
            send_data = {"webhookUrl": webhook_url, "message": msg_json}
            target_url = api_url
            self.send_log.insert(1.0, f"【云函数中转模式】\n云函数地址：{target_url}\n\n{json.dumps(send_data, ensure_ascii=False, indent=2)}")

        headers = {"Content-Type": "application/json"}
        if mode == "direct":
            token = self.token_entry.get().strip()
            if token:
                headers["AirScript-Token"] = token

        last_error = ""
        if self.retry_enabled.get():
            max_retries = self.retry_count.get()
            retry_interval = self.retry_interval.get()
        else:
            max_retries = 0
            retry_interval = 0

        for attempt in range(max_retries + 1):
            if self.stop_flag:
                self.resp_log.insert(1.0, "发送已终止")
                self._send_finished()
                return
            try:
                response = requests.post(target_url, json=send_data, headers=headers, timeout=10)
                result = f"状态码：{response.status_code}\n\n响应内容：\n{response.text}"
                self.resp_log.insert(1.0, result)
                self._send_finished()
                return
            except Exception as e:
                last_error = str(e)
                if self.stop_flag:
                    self.resp_log.insert(1.0, "发送已终止")
                    self._send_finished()
                    return
                if attempt < max_retries:
                    self.resp_log.insert(1.0, f"请求失败(第{attempt+1}次): {last_error}\n{retry_interval}秒后重试...\n")
                    time.sleep(retry_interval)
                else:
                    self.resp_log.insert(1.0, f"请求失败：\n{last_error}")
                    self._send_finished()

    def _send_finished(self):
        """发送完成后更新界面"""
        self.root.after(0, lambda: self.send_btn.configure(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_btn.configure(state=tk.DISABLED))
        self.root.after(0, self.save_config)
        self.is_sending = False

    # ===================== 配置保存/加载 =====================
    def save_config(self):
        config = {
            "mode": self.send_mode.get(),
            "api_url": self.api_entry.get(),
            "webhook_url": self.webhook_entry.get(),
            "message": self.msg_text.get(1.0, tk.END),
            "api_combo": self.api_combo.get(),
            "webhook_combo": self.webhook_combo.get(),
            "token": self.token_entry.get(),
            "api_urls": dict(API_URL_LIST),
            "webhook_urls": dict(WEBHOOK_URL_LIST),
            "retry_enabled": self.retry_enabled.get(),
            "retry_count": self.retry_count.get(),
            "retry_interval": self.retry_interval.get()
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def load_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    global API_URL_LIST, WEBHOOK_URL_LIST
                    if "api_urls" in config:
                        API_URL_LIST.clear()
                        API_URL_LIST.update(config["api_urls"])
                    if "webhook_urls" in config:
                        WEBHOOK_URL_LIST.clear()
                        WEBHOOK_URL_LIST.update(config["webhook_urls"])
                    return config
            except:
                return {}
        return {}

    def load_ui_config(self):
        if not self.config:
            self.token_entry.insert(0, "5ord2MaLBRMmneoFbvv8aR")
            return
        self.send_mode.set(self.config.get("mode", "proxy"))
        self.api_entry.insert(0, self.config.get("api_url", ""))
        self.webhook_entry.insert(0, self.config.get("webhook_url", ""))
        self.msg_text.insert(1.0, self.config.get("message", ""))
        self.api_combo.set(self.config.get("api_combo", ""))
        self.webhook_combo.set(self.config.get("webhook_combo", ""))
        token = self.config.get("token", "")
        self.token_entry.insert(0, token if token else "5ord2MaLBRMmneoFbvv8aR")
        self.retry_enabled.set(self.config.get("retry_enabled", True))
        self.retry_count.set(self.config.get("retry_count", 5))
        self.retry_interval.set(self.config.get("retry_interval", 2))
        self.switch_mode()

    # ===================== 地址编辑器 =====================
class AddressEditor:
    def __init__(self, parent, main_app):
        self.main_app = main_app
        self.editor_window = tk.Toplevel(parent)
        self.editor_window.title("地址编辑管理")
        self.editor_window.geometry("900x600")
        self.editor_window.resizable(True, True)
        self.editor_window.transient(parent)
        self.editor_window.grab_set()

        self.api_urls = dict(API_URL_LIST)
        self.webhook_urls = dict(WEBHOOK_URL_LIST)

        self.create_widgets()

    def create_widgets(self):
        notebook = ttk.Notebook(self.editor_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        api_frame = ttk.Frame(notebook)
        webhook_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text="云函数地址")
        notebook.add(webhook_frame, text="金山文档 Webhook")

        self.api_canvas = tk.Canvas(api_frame)
        self.api_scrollbar = ttk.Scrollbar(api_frame, orient=tk.VERTICAL, command=self.api_canvas.yview)
        self.api_content = ttk.Frame(self.api_canvas)
        self.api_canvas.configure(yscrollcommand=self.api_scrollbar.set)
        self.api_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.api_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.api_canvas.create_window((0, 0), window=self.api_content, anchor=tk.NW)
        self.api_content.bind("<Configure>", lambda e: self.api_canvas.configure(scrollregion=self.api_canvas.bbox(tk.ALL)))
        self.api_entries = []

        self.webhook_canvas = tk.Canvas(webhook_frame)
        self.webhook_scrollbar = ttk.Scrollbar(webhook_frame, orient=tk.VERTICAL, command=self.webhook_canvas.yview)
        self.webhook_content = ttk.Frame(self.webhook_canvas)
        self.webhook_canvas.configure(yscrollcommand=self.webhook_scrollbar.set)
        self.webhook_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.webhook_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.webhook_canvas.create_window((0, 0), window=self.webhook_content, anchor=tk.NW)
        self.webhook_content.bind("<Configure>", lambda e: self.webhook_canvas.configure(scrollregion=self.webhook_canvas.bbox(tk.ALL)))
        self.webhook_entries = []

        self.load_address_list(self.api_content, self.api_urls, self.api_entries, "api")
        self.load_address_list(self.webhook_content, self.webhook_urls, self.webhook_entries, "webhook")

        btn_frame = ttk.Frame(self.editor_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="保存", command=self.save_urls).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.editor_window.destroy).pack(side=tk.RIGHT)

    def load_address_list(self, parent, url_dict, entries_list, url_type):
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="名称", width=15, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="地址", font=("Arial", 9, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)

        for name, url in url_dict.items():
            row_frame = ttk.Frame(parent)
            row_frame.pack(fill=tk.X, pady=2)
            name_entry = ttk.Entry(row_frame, width=15)
            name_entry.insert(0, name)
            name_entry.pack(side=tk.LEFT, padx=2)
            url_entry = ttk.Entry(row_frame, width=50)
            url_entry.insert(0, url)
            url_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            ttk.Button(row_frame, text="删除", width=6,
                      command=lambda r=row_frame, n=name, t=url_type, el=entries_list: self.delete_url_row(r, n, t, el)).pack(side=tk.LEFT, padx=2)
            entries_list.append((name_entry, url_entry))

        add_frame = ttk.Frame(parent)
        add_frame.pack(fill=tk.X, pady=5)
        ttk.Label(add_frame, text="新增:", width=15).pack(side=tk.LEFT)
        new_name_entry = ttk.Entry(add_frame, width=15)
        new_name_entry.pack(side=tk.LEFT, padx=2)
        new_url_entry = ttk.Entry(add_frame, width=50)
        new_url_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(add_frame, text="添加", width=6,
                  command=lambda n=new_name_entry, u=new_url_entry, t=url_type, el=entries_list, p=parent: self.add_url_row(n, u, t, el, p)).pack(side=tk.LEFT, padx=2)

    def add_url_row(self, name_entry, url_entry, url_type, entries_list, parent):
        name = name_entry.get().strip()
        url = url_entry.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入名称")
            return
        if url_type == "api":
            self.api_urls[name] = url
        else:
            self.webhook_urls[name] = url
        name_entry.delete(0, tk.END)
        url_entry.delete(0, tk.END)

        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, pady=2)
        new_name_entry = ttk.Entry(row_frame, width=15)
        new_name_entry.insert(0, name)
        new_name_entry.pack(side=tk.LEFT, padx=2)
        new_url_entry = ttk.Entry(row_frame, width=50)
        new_url_entry.insert(0, url)
        new_url_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(row_frame, text="删除", width=6,
                  command=lambda r=row_frame, n=name, t=url_type, el=entries_list: self.delete_url_row(r, n, t, el)).pack(side=tk.LEFT, padx=2)
        entries_list.append((new_name_entry, new_url_entry))
        if url_type == "api":
            self.api_canvas.configure(scrollregion=self.api_canvas.bbox(tk.ALL))
        else:
            self.webhook_canvas.configure(scrollregion=self.webhook_canvas.bbox(tk.ALL))

    def delete_url_row(self, row_frame, name, url_type, entries_list):
        if url_type == "api":
            if name in self.api_urls:
                del self.api_urls[name]
        else:
            if name in self.webhook_urls:
                del self.webhook_urls[name]
        entries_list[:] = [ep for ep in entries_list if ep[0].get() != name]
        row_frame.destroy()

    def save_urls(self):
        self.api_urls.clear()
        self.webhook_urls.clear()
        saved_api = []
        saved_webhook = []
        for name_entry, url_entry in self.api_entries:
            try:
                name = name_entry.get().strip()
                url = url_entry.get().strip()
                if name:
                    self.api_urls[name] = url
                    saved_api.append(f"{name}: {url[:30]}...")
            except Exception as e:
                saved_api.append(f"错误: {e}")
        for name_entry, url_entry in self.webhook_entries:
            try:
                name = name_entry.get().strip()
                url = url_entry.get().strip()
                if name:
                    self.webhook_urls[name] = url
                    saved_webhook.append(f"{name}: {url[:30]}...")
            except Exception as e:
                saved_webhook.append(f"错误: {e}")
        global API_URL_LIST, WEBHOOK_URL_LIST
        API_URL_LIST.clear()
        API_URL_LIST.update(self.api_urls)
        WEBHOOK_URL_LIST.clear()
        WEBHOOK_URL_LIST.update(self.webhook_urls)
        self.main_app.api_combo.configure(values=list(API_URL_LIST.keys()))
        self.main_app.webhook_combo.configure(values=list(WEBHOOK_URL_LIST.keys()))
        self.main_app.save_config()
        self.editor_window.destroy()
        messagebox.showinfo("成功", f"地址已保存！\n云函数: {len(saved_api)}个\nWebhook: {len(saved_webhook)}个\n\n调试:\nAPI: {saved_api}\nWH: {saved_webhook}")

# ===================== 启动程序 =====================
if __name__ == "__main__":
    root = tk.Tk()
    app = WebhookSender(root)
    root.mainloop()