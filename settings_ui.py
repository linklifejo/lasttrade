import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import webbrowser

class SettingsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        from database_helpers import get_all_settings, save_all_settings
        self.get_all_settings = get_all_settings
        self.save_all_settings = save_all_settings
        self.entries = {}
        
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)

        # 1. 설정 폼 (스크롤 영역)
        self.canvas = tk.Canvas(self.main_frame, borderwidth=0, background="#f0f0f0")
        self.form_frame = ttk.Frame(self.canvas, padding="20")
        self.vsb = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="top", fill="both", expand=True)
        self.canvas_window = self.canvas.create_window((4,4), window=self.form_frame, anchor="nw")

        self.form_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # 타이틀
        ttk.Label(self.form_frame, text="⚡ 봇 환경설정", font=("Malgun Gothic", 16, "bold")).pack(pady=(0, 20), anchor="w")

        # 프리셋 버튼 섹션
        self.create_preset_buttons()

        # 설정 항목 생성
        self.create_form()
        
        # 2. 하단 설명 영역 (고정)
        self.bottom_frame = ttk.Frame(self, padding="10", relief="groove", borderwidth=2)
        self.bottom_frame.pack(side="bottom", fill="x")

        self.help_var = tk.StringVar(value="마우스를 설정 항목 위로 가져가면 여기에 자세한 설명이 표시됩니다.")
        self.lbl_help = tk.Label(self.bottom_frame, textvariable=self.help_var, 
                                 font=("Malgun Gothic", 11), fg="#333333", bg="#e6f2ff",
                                 wraplength=800, justify="left", height=3, anchor="nw", padx=10, pady=10)
        self.lbl_help.pack(fill="x", pady=(0, 10))

        self.create_buttons()
        self.load_settings()

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def update_help(self, text):
        self.help_var.set(text)

    def create_preset_buttons(self):
        """전략 프리셋 버튼 섹션 생성"""
        preset_frame = ttk.LabelFrame(self.form_frame, text="🎯 전략 프리셋 (원클릭 설정)", padding="15")
        preset_frame.pack(fill="x", pady=(0, 20))

        # 설명 레이블
        desc_label = ttk.Label(preset_frame, 
                              text="아래 버튼을 클릭하면 최적화된 설정값이 자동으로 적용됩니다.",
                              font=("Malgun Gothic", 9),
                              foreground="#666666")
        desc_label.pack(pady=(0, 10))

        # 버튼 프레임
        btn_container = ttk.Frame(preset_frame)
        btn_container.pack(fill="x")

        # 스타일 설정
        style = ttk.Style()
        style.configure("Preset.TButton", font=("Malgun Gothic", 10, "bold"), padding=10)

        # 4개 프리셋 버튼
        presets = [
            ("💧 몰빵 물타기", "molppang_water", "#2196F3"),
            ("🔥 몰빵 불타기", "molppang_fire", "#FF5722"),
            ("💧 분산 물타기", "bunsan_water", "#4CAF50"),
            ("🔥 분산 불타기", "bunsan_fire", "#FF9800")
        ]

        for i, (text, preset_id, color) in enumerate(presets):
            btn = ttk.Button(btn_container, text=text, 
                           command=lambda pid=preset_id: self.apply_preset(pid),
                           style="Preset.TButton")
            btn.pack(side="left", padx=5, expand=True, fill="x")

    def apply_preset(self, preset_id):
        """프리셋 설정값 적용"""
        presets = {
            "molppang_water": {
                "target_stock_count": 1,
                "trading_capital_ratio": 70.0,
                "split_buy_cnt": 10,
                "initial_buy_ratio": 10.0,
                "single_stock_strategy": "WATER",
                "single_stock_rate": 1.0,
                "take_profit_rate": 2.5,
                "stop_loss_rate": 10.0,  # 양수로 입력 (저장 시 음수 변환)
                "time_cut_minutes": 5,
                "time_cut_profit": 0.3,
                "use_trailing_stop": True,
                "trailing_stop_activation_rate": 1.5,
                "trailing_stop_callback_rate": 0.7,
                "upper_limit_rate": 29.0
            },
            "molppang_fire": {
                "target_stock_count": 1,
                "trading_capital_ratio": 70.0,
                "split_buy_cnt": 2,
                "initial_buy_ratio": 10.0,
                "single_stock_strategy": "FIRE",
                "single_stock_rate": 3.0,
                "take_profit_rate": 10.0,
                "stop_loss_rate": 5.0,
                "time_cut_minutes": 30,
                "time_cut_profit": 1.0,
                "use_trailing_stop": True,
                "trailing_stop_activation_rate": 1.5,
                "trailing_stop_callback_rate": 0.5,
                "upper_limit_rate": 29.5
            },
            "bunsan_water": {
                "target_stock_count": 5,
                "trading_capital_ratio": 70.0,
                "split_buy_cnt": 10,
                "initial_buy_ratio": 10.0,
                "single_stock_strategy": "WATER",
                "single_stock_rate": 1.0,
                "take_profit_rate": 3.5,
                "stop_loss_rate": 10.0,
                "time_cut_minutes": 15,
                "time_cut_profit": 0.5,
                "use_trailing_stop": True,
                "trailing_stop_activation_rate": 2.0,
                "trailing_stop_callback_rate": 1.0,
                "upper_limit_rate": 29.0
            },
            "bunsan_fire": {
                "target_stock_count": 5,
                "trading_capital_ratio": 70.0,
                "split_buy_cnt": 2,
                "initial_buy_ratio": 10.0,
                "single_stock_strategy": "FIRE",
                "single_stock_rate": 3.0,
                "take_profit_rate": 10.0,
                "stop_loss_rate": 5.0,
                "time_cut_minutes": 30,
                "time_cut_profit": 1.0,
                "use_trailing_stop": True,
                "trailing_stop_activation_rate": 1.5,
                "trailing_stop_callback_rate": 0.5,
                "upper_limit_rate": 29.5
            }
        }

        if preset_id not in presets:
            messagebox.showerror("Error", "알 수 없는 프리셋입니다.")
            return

        settings = presets[preset_id]
        
        # 설정값을 입력 필드에 적용
        for key, value in settings.items():
            if key in self.entries:
                widget, dtype = self.entries[key]
                widget.set(str(value))
        
        preset_names = {
            "molppang_water": "몰빵 물타기",
            "molppang_fire": "몰빵 불타기",
            "bunsan_water": "분산 물타기",
            "bunsan_fire": "분산 불타기"
        }
        
        messagebox.showinfo("프리셋 적용 완료", 
                          f"'{preset_names[preset_id]}' 설정이 적용되었습니다.\n\n"
                          f"아래 '💾 설정 저장' 버튼을 눌러 저장하세요.")

    def create_form(self):
        def add_section(title):
            lbl = ttk.Label(self.form_frame, text=title, font=("Malgun Gothic", 12, "bold"), foreground="#003399")
            lbl.pack(pady=(20, 10), anchor="w", fill="x")
            ttk.Separator(self.form_frame, orient="horizontal").pack(fill="x", pady=(0, 5))

        def add_field(key, label, tooltip_text, dtype="str", values=[]):
            row = ttk.Frame(self.form_frame)
            row.pack(fill="x", pady=4)
            
            lbl = ttk.Label(row, text=label, width=45, font=("Malgun Gothic", 10))
            lbl.pack(side="left")
            
            var = tk.StringVar()
            
            state = "normal"
            width = 20
            
            if dtype == "bool":
                combo_values = ["True", "False"]
                state = "readonly"
                width = 12
            elif dtype == "select":
                combo_values = values
                state = "readonly"
                width = 18
            else:
                combo_values = values
                state = "normal"
                width = 20
            
            widget = ttk.Combobox(row, textvariable=var, values=combo_values, state=state, width=width, font=("Consolas", 10))
            widget.pack(side="left")
            
            self.entries[key] = (widget, dtype)

            lbl.bind("<Enter>", lambda e, t=tooltip_text: self.update_help(t))
            widget.bind("<Enter>", lambda e, t=tooltip_text: self.update_help(t))
            row.bind("<Enter>", lambda e, t=tooltip_text: self.update_help(t))

        # --- 1. 기본 설정 ---
        add_section("📌 기본 설정")
        add_field("process_name", "투자 모드 (Trading Mode)", 
                 "투자를 진행할 서버를 선택합니다.\n[모의]: 연습용 / [실전]: 내 돈", 
                 "select", ["모의", "실전"])

        add_field("auto_start", "프로그램 시작 시 자동 실행 (Auto Start)", 
                 "True 선택 시, 프로그램이 켜지자마자 봇 매매 시작", "bool")

        add_field("target_stock_count", "최대 보유 종목 수 (Max Stocks)", 
                 "동시에 보유할 최대 종목 개수 (분산 투자)", "int", 
                 ["1", "3", "5", "10", "20", "30", "50"])

        add_field("trading_capital_ratio", "매매 자금 비율 (%) (Capital Ratio)", 
                 "총 자산 중 몇 %를 매매에 사용할까요?\n예: 70.0 입력 시 → 총 자산의 70%만 매매에 사용", "float", 
                 ["50.0", "60.0", "70.0", "80.0", "90.0", "100.0"])

        add_field("target_profit_amt", "일일 목표 수익금 (Daily Goal)", 
                 "오늘 이 금액 벌면 퇴근! (원 단위)", "int", 
                 ["10000", "50000", "100000", "300000", "500000", "1000000", "3000000"])

        # [변경] 음수 제거 -> 양수로 입력받음
        add_field("global_loss_rate", "일일 손실 한도 (%) (Loss Limit)", 
                 "계좌 전체 수익률이 이 값(양수)만큼 떨어지면 전량 매도합니다.\n예: 3.0 입력 시 -> -3.0% 도달 시 손절", "float", 
                 ["1.0", "2.0", "3.0", "5.0", "10.0", "20.0", "30.0", "99.0"])

        add_field("liquidation_time", "당일 청산 시간 (Liquidation Time)", 
                 "이 시간이 되면 묻지도 따지지도 않고 다 팝니다. (HH:MM)", "str", 
                 ["15:10", "15:15", "15:18", "15:20", "15:25", "15:28", "15:30"])

        # --- 2. 매수 전략 ---
        add_section("💰 매수 전략")
        add_field("split_buy_cnt", "분할 매수 횟수 (Split Count)", 
                 "최대 몇 번에 나누어 살까요?", "int", 
                 ["2", "3", "4", "5", "6", "7", "8", "9", "10"])

        add_field("single_stock_strategy", "단일 종목 전략 (Strategy)", 
                 "FIRE: 불타기(수익시 추매) / WATER: 물타기(손실시 추매)", "select", ["FIRE", "WATER"])

        add_field("single_stock_rate", "추가 매수 간격 (%) (Interval)", 
                 "몇 % 움직일 때마다 추가로 살까요?", "float", 
                 ["1.0", "2.0", "3.0", "4.0", "5.0", "6.0", "7.0", "8.0", "9.0", "10.0"])

        add_field("initial_buy_ratio", "초기 매수 비율 (%) (Initial Buy)", 
                 "첫 매수 시 종목당 할당 금액의 몇 %를 사용할까요?\n불타기: 10% 추천 / 물타기: 10% 추천", "float", 
                 ["10.0", "20.0", "25.0", "30.0", "33.3", "50.0", "100.0"])

        # --- 3. 매도 및 리스크 ---
        add_section("📉 매도 및 리스크 관리")
        add_field("take_profit_rate", "익절 기준 수익률 (%) (Take Profit)", 
                 "이만큼 먹으면 팝니다.", "float", 
                 ["1.0", "2.0", "3.0", "5.0", "10.0", "15.0", "20.0", "30.0"])

        # [변경] 음수 제거 -> 양수로 입력받음
        add_field("stop_loss_rate", "손절 기준 수익률 (%) (Stop Loss)", 
                 "이만큼 잃으면 칼같이 자릅니다. (양수 입력)\n예: 2.0 입력 시 -> -2.0% 도달 시 손절", "float", 
                 ["1.0", "2.0", "3.0", "5.0", "10.0", "15.0", "20.0"])

        add_field("early_stop_step", "조기 손절 시작 단계 (Early Stop Step)", 
                 "몇 단계부터 조기 손절(Early Stop)을 가동할까요?\n[3]: 3차 매수 후부터 손절 감시\n[4]: 4차 매수 후부터 손절 감시", "int", 
                 ["3", "4"])

        add_field("upper_limit_rate", "상한가 매도 기준 (%) (Upper Limit)", 
                 "상한가 근처 냄새 맡으면 미리 팝니다.", "float", 
                 ["20.0", "25.0", "28.0", "29.0", "29.5", "29.8"])

        add_field("time_cut_minutes", "타임컷 시간 (분) (Time Cut)", 
                 "이 시간 동안 재미 없으면 팝니다. (0: 안씀)", "int", 
                 ["0", "10", "20", "30", "40", "60", "90", "120"])

        add_field("time_cut_profit", "타임컷 수익률 조건 (%) (Time Cut Yield)", 
                 "타임컷 할 때, 최소 이정도는 벌었어야 팝니다.", "float", 
                 ["0.0", "0.5", "1.0", "1.5", "2.0"])

        # --- 4. 고급 필터 ---
        add_section("🔧 고급 필터")
        add_field("use_rsi_filter", "RSI 필터 사용 (Use RSI)", 
                 "보조지표 RSI를 매수 조건으로 쓸까요?", "bool")

        add_field("rsi_limit", "RSI 제한 값 (RSI Limit)", 
                 "RSI가 이 값 이하여야 삼", "int", 
                 ["30", "40", "50", "60", "70", "80"])

        add_field("use_trailing_stop", "트레일링 스탑 사용 (Trailing Stop)", 
                 "이익 보전 기능 사용 여부", "bool")

        add_field("trailing_stop_activation_rate", "TS 발동 기준 (%) (Activation)", 
                 "일단 수익률이 이만큼은 넘어야 감시 시작", "float", 
                 ["1.0", "2.0", "3.0", "4.0", "5.0", "10.0"])

        add_field("trailing_stop_callback_rate", "TS 하락 감지 (%) (Callback)", 
                 "최고점 대비 이만큼 빠지면 매도 실행", "float", 
                 ["0.5", "1.0", "1.5", "2.0", "2.5", "3.0", "5.0"])


    def create_buttons(self):
        btn_frame = self.bottom_frame
        style = ttk.Style()
        style.configure("Bold.TButton", font=("Malgun Gothic", 10, "bold"))

        btn_manual = ttk.Button(btn_frame, text="📄 사용설명서 보기", command=self.show_manual)
        btn_manual.pack(side="left")

        btn_save = ttk.Button(btn_frame, text="💾 설정 저장 (Save)", command=self.save_settings, style="Bold.TButton")
        btn_save.pack(side="right", padx=5)
        
        btn_load = ttk.Button(btn_frame, text="🔄 새로고침 (Reload)", command=self.load_settings)
        btn_load.pack(side="right", padx=5)

    def load_settings(self):
        try:
            data = self.get_all_settings()
            
            for key, (widget, dtype) in self.entries.items():
                if key in data:
                    val = data[key]
                    if dtype == 'bool':
                        widget.set(str(bool(val)))
                    elif dtype == 'select':
                        widget.set(str(val))
                    else:
                        # [중요] 손절 관련 값은 절대값(양수)으로 변환해서 보여줌
                        if key in ['global_loss_rate', 'stop_loss_rate']:
                            try:
                                val = abs(float(val))
                            except: pass
                        widget.set(str(val))
        except Exception as e:
            messagebox.showerror("Error", f"Load failed: {e}")

    def save_settings(self):
        new_data = {}
        try:
            # 먼저 기존 데이터 가져오기 (마이그레이션되지 않은 필드 보존용)
            new_data = self.get_all_settings()
        except: pass

        try:
            for key, (widget, dtype) in self.entries.items():
                val = widget.get()
                if not val.strip(): continue # 빈값은 무시

                if dtype == 'int': new_data[key] = int(val)
                elif dtype == 'float': 
                    f_val = float(val)
                    # [중요] 손절 관련 값은 음수로 변환해서 저장
                    if key in ['global_loss_rate', 'stop_loss_rate']:
                         f_val = -abs(f_val)
                    new_data[key] = f_val
                elif dtype == 'bool':
                    new_data[key] = (str(val) == "True")
                else: new_data[key] = str(val)
            
            # DB에 저장
            self.save_all_settings(new_data)
            messagebox.showinfo("Success", "설정이 DB에 저장되었습니다.\n봇이 실행 중이면 즉시 반영을 시도합니다.")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}\n(값을 올바르게 입력했는지 확인하세요)")

    def show_manual(self):
        readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.md')
        if os.path.exists(readme_path):
            os.startfile(readme_path)
        else:
            messagebox.showinfo("Manual", "README.md 파일이 없습니다.")
