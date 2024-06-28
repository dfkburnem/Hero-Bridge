import os
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from web3 import Web3
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import base64
import requests

# Configuration
CONFIG = {
    "rpc_addresses": {
        "serendale2": "https://klaytn.rpc.defikingdoms.com/",
        "crystalvale": "https://subnets.avax.network/defi-kingdoms/dfk-chain/rpc",
    },
    "contract_addresses": {
        "crystalvale": "0x739B1666c2956f601f095298132773074c3E184b",
        "serendale2": "0xEE258eF5F4338B37E9BA9dE6a56382AdB32056E2",
    },
    "chain_ids": {"crystalvale": 53935, "serendale2": 8217},
    "fees_in_gwei": {"serendale2": 0.0045, "crystalvale": 0.075},
}

w3_serendale2 = Web3(Web3.HTTPProvider(CONFIG["rpc_addresses"]["serendale2"]))
w3_crystalvale = Web3(Web3.HTTPProvider(CONFIG["rpc_addresses"]["crystalvale"]))


def load_abi(file_name):
    script_dir = os.getcwd()
    abi_file_path = os.path.join(script_dir, file_name)
    with open(abi_file_path, "r") as abi_file:
        return json.load(abi_file)


HERO_BRIDGE_ABI = load_abi("hero_bridge_abi.json")


def send_hero(
    origin_realm_contract_address,
    hero_id,
    destination_chain_id,
    bridge_fee_in_wei,
    private_key,
    nonce,
    gas_price_gwei,
    tx_timeout_seconds,
    rpc_address,
    ui_update_function,
):
    w3 = Web3(Web3.HTTPProvider(rpc_address))
    account = w3.eth.account.from_key(private_key)
    w3.eth.default_account = account.address

    origin_realm_contract_address = Web3.to_checksum_address(
        origin_realm_contract_address
    )
    contract = w3.eth.contract(
        address=origin_realm_contract_address, abi=HERO_BRIDGE_ABI
    )

    tx = contract.functions.sendHero(hero_id, destination_chain_id)

    tx = tx.build_transaction(
        {
            "maxFeePerGas": w3.to_wei(gas_price_gwei["maxFeePerGas"], "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(
                gas_price_gwei["maxPriorityFeePerGas"], "gwei"
            ),
            "value": bridge_fee_in_wei,
            "nonce": nonce,
        }
    )

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)
    w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    ui_update_function("Transaction successfully sent!")
    tx_receipt = w3.eth.wait_for_transaction_receipt(
        transaction_hash=signed_tx.hash, timeout=tx_timeout_seconds, poll_latency=2
    )
    ui_update_function("Transaction mined!")

    return tx_receipt


def parse_class_input(user_input):
    user_input = ", ".join(str(item) for item in user_input)
    if user_input.strip().lower() == "none":
        return None
    main_classes = []
    input_parts = user_input.replace(" ", "").split(",")
    for part in input_parts:
        if "-" in part:
            start, end = part.split("-")
            main_classes.extend(range(int(start), int(end) + 1))
        elif part.startswith("[") and part.endswith("]"):
            class_list = part[1:-1].split(";")
            main_classes.extend([int(cls) for cls in class_list])
        else:
            main_classes.append(int(part))
    return main_classes


class HeroSearchApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Hero Bridge Tool")
        self.master.configure(bg="black")
        self.master.geometry("1500x980")
        self.persistent_selected_heroes = {}
        self.configure_style()

        # Create and place a container frame to hold all UI elements
        self.container = ttk.Frame(self.master, style="TFrame")
        self.container.pack(fill="both", expand=True)
        self.create_frames()
        self.init_class_and_ability_mappings()
        self.main_class_selections = set()
        self.sub_class_selections = set()
        self.selected_heroes = []
        self.init_ui_elements()

    def configure_style(self):
        style = ttk.Style()
        style.configure("TFrame", background="black")
        style.configure(
            "TButton",
            background="black",
            foreground="white",
            borderwidth=1,
            focuscolor="none",
        )
        style.configure("TLabel", background="black", foreground="white")
        style.map(
            "TButton",
            background=[("active", "grey"), ("!disabled", "black")],
            foreground=[("active", "white")],
        )
        style.configure("TScale", background="black", foreground="white")
        style.configure(
            "TRadiobutton",
            background="black",
            foreground="white",
            indicatorbackground="black",
            indicatoron=False,
        )

    def create_frames(self):
        self.search_frame = ttk.Frame(self.container, style="TFrame")
        self.search_frame.grid(row=0, column=0, sticky="nsew")

        self.results_frame = ttk.Frame(self.container, style="TFrame")
        self.results_frame.grid(row=0, column=1, sticky="nsew", padx=10)

        # Configure row and column weights for resizing
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)  # Fixed width for search_frame
        self.container.grid_columnconfigure(
            1, weight=1
        )  # Expandable width for results_frame

    def init_class_and_ability_mappings(self):
        self.rarity_map = {
            0: "common",
            1: "uncommon",
            2: "rare",
            3: "legendary",
            4: "mythic",
        }

        self.class_names = {
            0: "Warrior",
            1: "Knight",
            2: "Thief",
            3: "Archer",
            4: "Priest",
            5: "Wizard",
            6: "Monk",
            7: "Pirate",
            8: "Berserker",
            9: "Seer",
            10: "Legionnaire",
            11: "Scholar",
            16: "Paladin",
            17: "DarkKnight",
            18: "Summoner",
            19: "Ninja",
            20: "Shapeshifter",
            21: "Bard",
            24: "Dragoon",
            25: "Sage",
            26: "Spellbow",
            28: "DreadKnight",
        }

        self.ability_names = {
            0: "B1",
            1: "B2",
            2: "B3",
            3: "B4",
            4: "B5",
            5: "B6",
            6: "B7",
            7: "B8",
            16: "A1",
            17: "A2",
            18: "A3",
            19: "A4",
            24: "E1",
            25: "E2",
            28: "T1",
        }

    def init_ui_elements(self):
        self.init_class_selection(
            self.search_frame,
            "Select Main Class",
            self.main_class_selections,
            0,
            is_main_class=True,
        )
        self.init_class_selection(
            self.search_frame,
            "Select Sub Class",
            self.sub_class_selections,
            1,
            is_main_class=False,
        )
        self.init_summon_selection(self.search_frame)
        self.init_generation_selection(self.search_frame)
        self.init_rarity_selection(self.search_frame)
        self.init_level_selection(self.search_frame)
        self.init_realm_selection(self.search_frame)
        self.init_profession_selection(self.search_frame)
        self.init_password_entry(self.search_frame)
        self.init_search_button(self.search_frame)
        self.init_select_all_button(self.search_frame)
        self.init_bridge_selected_button(self.search_frame)
        self.init_results_area()
        self.init_selected_heroes_area()

    def init_results_area(self):
        self.results_text = scrolledtext.ScrolledText(
            self.results_frame, width=150, height=10, bg="black", fg="white"
        )
        self.results_text.pack(fill="both", expand=True)
        self.results_text.config(state=tk.DISABLED)

    def init_selected_heroes_area(self):
        self.selected_heroes_frame = ttk.Frame(self.results_frame, style="TFrame")
        self.selected_heroes_frame.pack(fill="both", expand=True)

        self.selected_heroes_label = ttk.Label(
            self.selected_heroes_frame, text="Selected Heroes", style="TLabel"
        )
        self.selected_heroes_label.pack(anchor="w", padx=5)

        self.selected_heroes_text = scrolledtext.ScrolledText(
            self.selected_heroes_frame, width=150, height=5, bg="black", fg="white"
        )
        self.selected_heroes_text.pack(fill="both", expand=True)
        self.selected_heroes_text.config(state=tk.DISABLED)

    def log_to_ui(self, message):
        self.master.after(0, lambda: self._log_to_ui(message))

    def _log_to_ui(self, message):
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, f"{message}\n")
        self.results_text.see(tk.END)
        self.results_text.config(state=tk.DISABLED)

    def async_log_to_ui(self, message):
        threading.Thread(target=self.log_to_ui, args=(message,)).start()

    def update_results_area(self, data):
        if data["action"] == "remove":
            del self.persistent_selected_heroes[data["hero_id"]]
            self.update_selected_heroes_area()  # Refresh the list of selected heroes
            self.results_text.insert(
                tk.END, f"Hero ID {data['hero_id']} bridged successfully.\n"
            )

    def init_profession_selection(self, master):
        ttk.Label(master, text="Select Profession:").grid(
            row=13, column=0, columnspan=4, sticky="w", padx=5, pady=(10, 0)
        )

        buttons_frame = ttk.Frame(master)
        buttons_frame.grid(row=14, column=0, columnspan=4, sticky="ew", padx=5)

        self.foraging_var = tk.IntVar(value=0)
        self.fishing_var = tk.IntVar(value=0)
        self.gardening_var = tk.IntVar(value=0)
        self.mining_var = tk.IntVar(value=0)

        self.foraging_button = tk.Button(
            buttons_frame,
            text="Foraging",
            bg="black",
            fg="white",
            width=15,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=lambda: self.toggle_profession_selection(
                self.foraging_var, self.foraging_button
            ),
        )
        self.foraging_button.grid(row=0, column=0, sticky="ew", padx=5)

        self.fishing_button = tk.Button(
            buttons_frame,
            text="Fishing",
            bg="black",
            fg="white",
            width=15,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=lambda: self.toggle_profession_selection(
                self.fishing_var, self.fishing_button
            ),
        )
        self.fishing_button.grid(row=0, column=1, sticky="ew", padx=5)

        self.gardening_button = tk.Button(
            buttons_frame,
            text="Gardening",
            bg="black",
            fg="white",
            width=15,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=lambda: self.toggle_profession_selection(
                self.gardening_var, self.gardening_button
            ),
        )
        self.gardening_button.grid(row=0, column=2, sticky="ew", padx=5)

        self.mining_button = tk.Button(
            buttons_frame,
            text="Mining",
            bg="black",
            fg="white",
            width=15,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=lambda: self.toggle_profession_selection(
                self.mining_var, self.mining_button
            ),
        )
        self.mining_button.grid(row=0, column=3, sticky="ew", padx=5)

        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)
        buttons_frame.grid_columnconfigure(2, weight=1)
        buttons_frame.grid_columnconfigure(3, weight=1)

    def toggle_profession_selection(self, profession_var, button):
        if profession_var.get() == 1:
            profession_var.set(0)
            button.config(
                bg="black",
                fg="white",
                highlightbackground="white",
                highlightthickness=2,
            )
        else:
            profession_var.set(1)
            button.config(
                bg="green",
                fg="white",
                highlightbackground="white",
                highlightthickness=2,
            )

    def init_realm_selection(self, master):
        ttk.Label(master, text="Select Realm:").grid(
            row=11, column=0, columnspan=4, sticky="w", padx=5, pady=(10, 0)
        )

        buttons_frame = ttk.Frame(master)
        buttons_frame.grid(row=12, column=0, columnspan=4, sticky="ew", padx=5)

        self.cv_var = tk.IntVar(value=0)
        self.sd_var = tk.IntVar(value=0)

        self.cv_button = tk.Button(
            buttons_frame,
            text="Crystalvale",
            bg="black",
            fg="white",
            width=15,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=lambda: self.toggle_realm_selection(self.cv_var, self.cv_button),
        )
        self.cv_button.grid(row=0, column=0, sticky="ew", padx=5)

        self.sd_button = tk.Button(
            buttons_frame,
            text="Serendale",
            bg="black",
            fg="white",
            width=15,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=lambda: self.toggle_realm_selection(self.sd_var, self.sd_button),
        )
        self.sd_button.grid(row=0, column=1, sticky="ew", padx=5)

        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)

    def toggle_realm_selection(self, realm_var, button):
        if realm_var.get() == 1:
            realm_var.set(0)
            button.config(
                bg="black",
                fg="white",
                highlightbackground="white",
                highlightthickness=2,
            )
        else:
            realm_var.set(1)
            button.config(
                bg="green",
                fg="white",
                highlightbackground="white",
                highlightthickness=2,
            )

    def init_level_selection(self, master):
        ttk.Label(master, text="Hero Level Range:").grid(
            row=22, column=0, columnspan=3, sticky="w", padx=5
        )

        self.min_level_var = tk.IntVar(value=1)
        ttk.Label(master, text="Min:").grid(row=23, column=0, sticky="w", padx=5)
        self.min_level_scale = ttk.Scale(
            master,
            from_=1,
            to=20,
            orient="horizontal",
            variable=self.min_level_var,
            command=self.update_level_min_label,
        )
        self.min_level_scale.grid(row=23, column=1, sticky="ew", padx=5)
        self.min_level_label = ttk.Label(master, textvariable=self.min_level_var)
        self.min_level_label.grid(row=23, column=2, sticky="w", padx=5)

        self.max_level_var = tk.IntVar(value=20)
        ttk.Label(master, text="Max:").grid(row=24, column=0, sticky="w", padx=5)
        self.max_level_scale = ttk.Scale(
            master,
            from_=1,
            to=20,
            orient="horizontal",
            variable=self.max_level_var,
            command=self.update_level_max_label,
        )
        self.max_level_scale.grid(row=24, column=1, sticky="ew", padx=5)
        self.max_level_label = ttk.Label(master, textvariable=self.max_level_var)
        self.max_level_label.grid(row=24, column=2, sticky="w", padx=5)

    def update_level_min_label(self, event=None):
        self.min_level_var.set(int(self.min_level_scale.get()))

    def update_level_max_label(self, event=None):
        self.max_level_var.set(int(self.max_level_scale.get()))

    def init_generation_selection(self, master):
        ttk.Label(master, text="Generation Range:").grid(
            row=19, column=0, columnspan=3, sticky="w", padx=5, pady=0
        )

        self.min_generation_var = tk.IntVar(value=0)
        ttk.Label(master, text="Min:").grid(
            row=20, column=0, sticky="w", padx=5, pady=0
        )
        self.min_generation_scale = ttk.Scale(
            master,
            from_=0,
            to=69,
            orient="horizontal",
            variable=self.min_generation_var,
            command=self.update_generation_min_label,
        )
        self.min_generation_scale.grid(row=20, column=1, sticky="ew", padx=5, pady=0)
        self.min_generation_label = ttk.Label(
            master, textvariable=self.min_generation_var
        )
        self.min_generation_label.grid(row=20, column=2, sticky="w", padx=5, pady=0)

        self.max_generation_var = tk.IntVar(value=69)
        ttk.Label(master, text="Max:").grid(
            row=21, column=0, sticky="w", padx=5, pady=0
        )
        self.max_generation_scale = ttk.Scale(
            master,
            from_=0,
            to=69,
            orient="horizontal",
            variable=self.max_generation_var,
            command=self.update_generation_max_label,
        )
        self.max_generation_scale.grid(row=21, column=1, sticky="ew", padx=5, pady=0)
        self.max_generation_label = ttk.Label(
            master, textvariable=self.max_generation_var
        )
        self.max_generation_label.grid(row=21, column=2, sticky="w", padx=5, pady=0)

    def init_class_selection(
        self, master, label_text, selection_set, offset, is_main_class=True
    ):
        ttk.Label(master, text=label_text).grid(
            row=offset * 6, column=0, columnspan=4, sticky="w"
        )

        buttons_frame = ttk.Frame(master)
        buttons_frame.grid(row=1 + offset * 6, column=0, columnspan=4, sticky="ew")

        class_buttons = {}

        for index, (class_number, class_name) in enumerate(self.class_names.items()):
            btn = tk.Button(
                buttons_frame,
                text=f"{class_name}",
                bg="black",
                fg="white",
                width=15,
                highlightbackground="white",
                highlightcolor="white",
                highlightthickness=2,
                bd=5,
                command=lambda cn=class_number, s=selection_set: self.toggle_class_selection(
                    cn, s, class_buttons
                ),
            )
            btn.grid(
                row=(index // 4 + 1), column=index % 4, sticky="ew", padx=5, pady=2
            )
            class_buttons[class_number] = btn

        tk.Button(
            buttons_frame,
            text="All",
            command=lambda: self.select_classes(
                class_buttons, selection_set, list(self.class_names.keys())
            ),
        ).grid(row=0, column=0, sticky="ew", padx=5)
        tk.Button(
            buttons_frame,
            text="Basic",
            command=lambda: self.select_classes(
                class_buttons, selection_set, list(range(0, 12))
            ),
        ).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(
            buttons_frame,
            text="Advanced",
            command=lambda: self.select_classes(
                class_buttons, selection_set, list(range(16, 22))
            ),
        ).grid(row=0, column=2, sticky="ew", padx=5)
        tk.Button(
            buttons_frame,
            text="Elite",
            command=lambda: self.select_classes(
                class_buttons, selection_set, list(range(24, 27))
            ),
        ).grid(row=0, column=3, sticky="ew", padx=5)

        buttons_frame.grid_columnconfigure(tuple(range(4)), weight=1)

    def init_summon_selection(self, master):
        ttk.Label(master, text="Summons Range:").grid(
            row=16, column=0, columnspan=3, sticky="w", padx=5
        )

        self.min_summon_var = tk.IntVar(value=0)
        ttk.Label(master, text="Min:").grid(row=17, column=0, sticky="w", padx=5)
        self.min_summon_scale = ttk.Scale(
            master,
            from_=0,
            to_=11,
            orient="horizontal",
            variable=self.min_summon_var,
            command=self.update_summon_min_label,
        )
        self.min_summon_scale.grid(row=17, column=1, sticky="ew", padx=5)
        self.min_summon_label = ttk.Label(master, textvariable=self.min_summon_var)
        self.min_summon_label.grid(row=17, column=2, sticky="w", padx=5)

        self.max_summon_var = tk.IntVar(value=11)
        ttk.Label(master, text="Max:").grid(row=18, column=0, sticky="w", padx=5)
        self.max_summon_label = ttk.Label(master, textvariable=self.max_summon_var)
        self.max_summon_label.grid(row=18, column=2, sticky="w", padx=5)
        self.max_summon_scale = ttk.Scale(
            master,
            from_=0,
            to_=11,
            orient="horizontal",
            variable=self.max_summon_var,
            command=self.update_summon_max_label,
        )
        self.max_summon_scale.grid(row=18, column=1, sticky="ew", padx=5)

    def init_password_entry(self, master):
        self.password_label = ttk.Label(
            self.search_frame, text="Password:", style="TLabel"
        )
        self.password_label.grid(row=16, column=3, sticky="w", padx=5)
        self.password_entry = ttk.Entry(self.search_frame, show="*")
        self.password_entry.grid(row=17, column=3, sticky="ew", padx=5)

    def init_search_button(self, master):
        self.search_button = tk.Button(
            self.search_frame,
            text="Search",
            bg="green",
            fg="white",
            width=20,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=self.perform_search,
        )
        self.search_button.grid(row=18, column=3, rowspan=2, sticky="ew", padx=5)

    def init_select_all_button(self, master):
        self.select_all_button = tk.Button(
            self.search_frame,
            text="Select All",
            bg="blue",
            fg="white",
            width=20,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=self.select_all_heroes,
        )
        self.select_all_button.grid(row=20, column=3, rowspan=2, sticky="ew", padx=5)

    def init_bridge_selected_button(self, master):
        self.bridge_selected_button = tk.Button(
            self.search_frame,
            text="Bridge Selected",
            bg="red",
            fg="white",
            width=20,
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=2,
            bd=5,
            command=self.bridge_heroes,
        )
        self.bridge_selected_button.grid(
            row=22, column=3, rowspan=2, sticky="ew", padx=5
        )

    def init_rarity_selection(self, master):
        self.min_rarity_var = tk.IntVar(value=0)
        self.max_rarity_var = tk.IntVar(value=4)

        ttk.Label(master, text="Rarity Range:").grid(
            row=25, column=0, columnspan=3, sticky="w", padx=5
        )

        self.min_rarity_name = tk.StringVar(value="common")
        self.max_rarity_name = tk.StringVar(value="mythic")

        ttk.Label(master, text="Min:").grid(row=26, column=0, sticky="w", padx=5)
        self.min_rarity_label = ttk.Label(
            master, textvariable=self.min_rarity_name, width=10
        )
        self.min_rarity_label.grid(row=26, column=2, sticky="ew")

        self.min_rarity_scale = ttk.Scale(
            master,
            from_=0,
            to=4,
            orient="horizontal",
            variable=self.min_rarity_var,
            command=lambda e: self.update_rarity_labels(),
        )
        self.min_rarity_scale.grid(row=26, column=1, sticky="ew", padx=5)

        ttk.Label(master, text="Max:").grid(row=27, column=0, sticky="w", padx=5)
        self.max_rarity_label = ttk.Label(
            master, textvariable=self.max_rarity_name, width=10
        )
        self.max_rarity_label.grid(row=27, column=2, sticky="ew")

        self.max_rarity_scale = ttk.Scale(
            master,
            from_=0,
            to=4,
            orient="horizontal",
            variable=self.max_rarity_var,
            command=lambda e: self.update_rarity_labels(),
        )
        self.max_rarity_scale.grid(row=27, column=1, sticky="ew", padx=5)

        master.grid_columnconfigure(1, weight=1)
        master.grid_columnconfigure(2, weight=1)

    def update_rarity_labels(self):
        rarity_map = {
            0: "common",
            1: "uncommon",
            2: "rare",
            3: "legendary",
            4: "mythic",
        }
        self.min_rarity_name.set(f"{rarity_map[self.min_rarity_var.get()]:<10}")
        self.max_rarity_name.set(f"{rarity_map[self.max_rarity_var.get()]:<10}")

    def update_summon_min_label(self, event=None):
        self.min_summon_var.set(int(self.min_summon_scale.get()))

    def update_summon_max_label(self, event=None):
        self.max_summon_var.set(int(self.max_summon_scale.get()))

    def update_generation_min_label(self, event=None):
        self.min_generation_var.set(int(self.min_generation_scale.get()))

    def update_generation_max_label(self, event=None):
        self.max_generation_var.set(int(self.max_generation_scale.get()))

    def update_selected_heroes_area(self):
        self.selected_heroes_text.config(state=tk.NORMAL)
        self.selected_heroes_text.delete(1.0, tk.END)

        for hero in self.persistent_selected_heroes.values():
            (
                hero_info,
                hero_abilities,
                mainclassvalue,
                subclassvalue,
                realminfo,
                raritytag,
                level,
                profession,
            ) = self.construct_detailed_info(hero)
            self.insert_hero_info_and_abilities_inline(
                self.selected_heroes_text,
                hero_info,
                hero_abilities,
                mainclassvalue,
                subclassvalue,
                realminfo,
                raritytag,
                level,
                profession,
                None,
            )

        self.selected_heroes_text.config(state=tk.DISABLED)

    def toggle_class_selection(self, class_number, selection_set, class_buttons):
        if class_number in selection_set:
            selection_set.remove(class_number)
        else:
            selection_set.add(class_number)
        bg_color = "green" if class_number in selection_set else "black"
        class_buttons[class_number].config(
            bg=bg_color, fg="white", highlightbackground="white", highlightthickness=2
        )

    def select_classes(self, class_buttons, selection_set, class_range):
        all_selected = all(
            class_number in selection_set for class_number in class_range
        )
        for class_number in class_range:
            if class_number in class_buttons:
                if all_selected:
                    selection_set.remove(class_number)
                    class_buttons[class_number].config(
                        bg="black",
                        fg="white",
                        highlightbackground="white",
                        highlightthickness=2,
                    )
                else:
                    selection_set.add(class_number)
                    class_buttons[class_number].config(
                        bg="green",
                        fg="white",
                        highlightbackground="white",
                        highlightthickness=2,
                    )

    def search_heroes(
        self,
        account_address,
        main_class,
        sub_class,
        min_summon,
        max_summon,
        min_gen,
        max_gen,
        min_rarity,
        max_rarity,
        min_level,
        max_level,
        cv,
        sd,
        foraging,
        fishing,
        gardening,
        mining,
    ):
        main_classes = parse_class_input(main_class) if main_class else []
        sub_classes = parse_class_input(sub_class) if sub_class else []

        min_summons = int(min_summon) if min_summon is not None else 0
        max_summons = int(max_summon) if max_summon is not None else 999

        min_generation = int(min_gen) if min_gen is not None else 0
        max_generation = int(max_gen) if max_gen is not None else 999

        min_rarity = int(min_rarity) if min_rarity is not None else 0
        max_rarity = int(max_rarity) if max_rarity is not None else 4

        min_level = int(min_level) if min_level is not None else 0
        max_level = int(max_level) if max_level is not None else 20

        networks = []
        if cv:
            networks.append("dfk")
        if sd:
            networks.append("kla")

        professions = []
        if foraging:
            professions.append("foraging")
        if fishing:
            professions.append("fishing")
        if gardening:
            professions.append("gardening")
        if mining:
            professions.append("mining")

        all_heroes = []
        continue_search = True
        skip_number = 0
        while continue_search:
            url = "https://api.defikingdoms.com/graphql"
            query = """
            query getHeroes($account_address: String!, $skip_number: Int!, $min_summons: Int, $max_summons: Int, $main_classes: [Int], $sub_classes: [Int], $max_generation: Int, $min_generation: Int, $max_rarity: Int, $min_rarity: Int, $min_level: Int, $max_level: Int, $networks: [String], $professions: [String]){
                heroes(first: 250, skip: $skip_number, orderBy: id, orderDirection: desc, where: {owner: $account_address, summonsRemaining_gte: $min_summons, summonsRemaining_lte: $max_summons, mainClass_in: $main_classes, subClass_in: $sub_classes, generation_lte: $max_generation, generation_gte: $min_generation, rarity_lte: $max_rarity, rarity_gte: $min_rarity, level_gte: $min_level, level_lte: $max_level, network_in: $networks, professionStr_in: $professions}) {
                    id
                    mainClass
                    subClass
                    summonsRemaining
                    passive1
                    passive2
                    active1
                    active2
                    generation
                    rarity
                    level
                    network
                    professionStr
                }
            }
            """
            variables = {
                "account_address": account_address,
                "skip_number": skip_number,
                "min_summons": min_summons,
                "max_summons": max_summons,
                "main_classes": main_classes or [],
                "sub_classes": sub_classes or [],
                "max_generation": max_generation,
                "min_generation": min_generation,
                "max_rarity": max_rarity,
                "min_rarity": min_rarity,
                "min_level": min_level,
                "max_level": max_level,
                "networks": networks,
                "professions": professions,
            }
            response = requests.post(url, json={"query": query, "variables": variables})
            if response.status_code == 200:
                json_data = response.json()
                if "data" in json_data and "heroes" in json_data["data"]:
                    current_heroes = json_data["data"]["heroes"]
                    all_heroes.extend(current_heroes)
                    if len(current_heroes) < 250:
                        continue_search = False
                    else:
                        skip_number += 250
                else:
                    self.async_log_to_ui(f"No data found in response: {json_data}")
                    continue_search = False
            else:
                self.async_log_to_ui(
                    f"Failed to fetch heroes, Status Code: {response.status_code}, Response: {response.text}"
                )
                continue_search = False

        return all_heroes

    def perform_search(self):
        password = self.password_entry.get()
        script_dir = os.getcwd()
        key_file_name = next(
            (f for f in os.listdir(script_dir) if f.endswith(".key")), None
        )
        private_key = self.decrypt_key(
            os.path.join(script_dir, key_file_name), password
        )
        if not private_key:
            self.async_log_to_ui("Failed to decrypt private key.")
            return

        account_address = w3_serendale2.eth.account.from_key(private_key).address
        all_heroes = self.search_heroes(
            account_address,
            self.main_class_selections,
            self.sub_class_selections,
            self.min_summon_var.get(),
            self.max_summon_var.get(),
            self.min_generation_var.get(),
            self.max_generation_var.get(),
            self.min_rarity_var.get(),
            self.max_rarity_var.get(),
            self.min_level_var.get(),
            self.max_level_var.get(),
            self.cv_var.get(),
            self.sd_var.get(),
            self.foraging_var.get(),
            self.fishing_var.get(),
            self.gardening_var.get(),
            self.mining_var.get(),
        )
        self.display_results(all_heroes)
        self.update_selected_heroes_area()
        self.async_log_to_ui(f"Total heroes found: {len(all_heroes)}")

    def display_results(self, all_heroes):
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.hero_checkboxes = []

        for hero in all_heroes:
            var = tk.IntVar(
                value=1 if hero["id"] in self.persistent_selected_heroes else 0
            )
            checkbox = ttk.Checkbutton(
                self.results_text,
                text="",
                variable=var,
                command=lambda h=hero, v=var: self.update_persistent_selection(h, v),
            )
            self.results_text.window_create(tk.END, window=checkbox)
            self.hero_checkboxes.append((var, hero))

            (
                hero_info,
                hero_abilities,
                mainclassvalue,
                subclassvalue,
                realminfo,
                raritytag,
                level,
                profession,
            ) = self.construct_detailed_info(hero)
            self.insert_hero_info_and_abilities_inline(
                self.results_text,
                hero_info,
                hero_abilities,
                mainclassvalue,
                subclassvalue,
                realminfo,
                raritytag,
                level,
                profession,
                checkbox,
            )

        self.results_text.config(state=tk.DISABLED)
        self.update_selected_heroes_area()

    def update_persistent_selection(self, hero, var):
        if var.get() == 1:
            self.persistent_selected_heroes[hero["id"]] = hero
        elif hero["id"] in self.persistent_selected_heroes:
            del self.persistent_selected_heroes[hero["id"]]

        self.update_selected_heroes_area()

    def select_all_heroes(self):
        all_selected = all(var.get() == 1 for var, _ in self.hero_checkboxes)

        for var, hero in self.hero_checkboxes:
            var.set(0 if all_selected else 1)
            self.update_persistent_selection(hero, var)

        self.update_selected_heroes_area()

    def display_selected_heroes(self):
        self.bridge_results_text.delete(1.0, tk.END)
        for hero in self.persistent_selected_heroes.values():
            (
                hero_info,
                hero_abilities,
                mainclassvalue,
                subclassvalue,
                realminfo,
                raritytag,
                level,
                profession,
            ) = self.construct_detailed_info(hero)
            self.insert_hero_info_and_abilities_inline(
                self.bridge_results_text,
                hero_info,
                hero_abilities,
                mainclassvalue,
                subclassvalue,
                realminfo,
                raritytag,
                level,
                profession,
                None,
            )

    def insert_hero_info_and_abilities_inline(
        self,
        text_widget,
        hero_info,
        abilities_info,
        mainClassValue,
        subclassValue,
        priceinfo,
        rarity_tag,
        level,
        profession,
        checkbox,
    ):
        # Configure text tags
        tags = {
            "common": "white",
            "uncommon": "lightgreen",
            "rare": "blue",
            "legendary": "orange",
            "mythic": "purple",
            "basic_class": "white",
            "advanced_class": "lightgreen",
            "elite_class": "#87CEEB",
            "transcendent_class": "violet",
        }
        for tag, color in tags.items():
            self.results_text.tag_config(tag, foreground=color)
            self.selected_heroes_text.tag_config(tag, foreground=color)

        # Determine class tags
        class_tag_mappings = {
            range(0, 12): "basic_class",
            range(16, 22): "advanced_class",
            range(24, 27): "elite_class",
            (28,): "transcendent_class",
        }
        main_class_tag = next(
            (tag for rng, tag in class_tag_mappings.items() if mainClassValue in rng),
            "basic_class",
        )
        subclass_tag = next(
            (tag for rng, tag in class_tag_mappings.items() if subclassValue in rng),
            "basic_class",
        )

        # Parse hero_info
        parts = hero_info.split(" Main Class: ")
        parts2 = hero_info.split(" | ", 1)
        id_label = parts2[0]
        id_label_text, id_number = id_label.split(" ", 1)

        main_class_and_beyond = parts[1]
        main_class_name, after_main_class = main_class_and_beyond.split(", ", 1)
        subclass_name, after_subclass = after_main_class.split(", ", 1)
        subclass_label, subclass_class = subclass_name.split(":", 1)
        parts = hero_info.split(", ")
        gen_label, gen_number = parts[2].split(":", 1)
        summons_label, summons_number = parts[3].split(":", 1)

        # Format display strings
        fixed_width = 13
        profession_width = 9
        small_width = 2
        summons_width = 3
        main_class_display = f"{main_class_name:<{fixed_width}}"
        subclass_display = f"{subclass_class:<{fixed_width}}"
        gen_display = f"{gen_number:<{small_width}}"
        level_display = f"{str(level):<{small_width}}"
        summons_display = f"{summons_number:<{summons_width}}"
        profession_display = f"{profession:<{profession_width}}"

        # Insert text into text_widget
        if checkbox:
            text_widget.window_create(tk.END, window=checkbox)
        text_widget.insert(tk.END, id_label_text + " ")
        text_widget.insert(tk.END, id_number, rarity_tag)
        text_widget.insert(tk.END, " | Main Class: ")
        text_widget.insert(tk.END, main_class_display, main_class_tag)
        text_widget.insert(tk.END, "| Sub Class:")
        text_widget.insert(tk.END, subclass_display, subclass_tag)
        text_widget.insert(
            tk.END,
            f" | Level: {level_display} | Profession: {profession_display} | Gen: {gen_display} | Summons: {summons_display}",
        )

        for ability_key, ability_value in abilities_info.items():
            text_widget.insert(tk.END, f" | {ability_key}: ")
            ability_name = self.ability_names.get(ability_value, "Unknown")
            ability_tag = next(
                (
                    tag
                    for rng, tag in class_tag_mappings.items()
                    if ability_value in rng
                ),
                "basic_class",
            )
            text_widget.insert(tk.END, ability_name, ability_tag)

        text_widget.insert(tk.END, priceinfo)
        text_widget.insert(tk.END, "\n")

    def construct_detailed_info(self, hero):
        fixed_id_width = 13
        main_class_value = hero.get("mainClass")
        subclass_value = hero.get("subClass")

        main_class_name = self.class_names.get(main_class_value, "Unknown Class")
        sub_class_name = self.class_names.get(subclass_value, "Unknown Class")

        rarity = hero.get("rarity", 0)
        rarity_tags = {
            0: "common",
            1: "uncommon",
            2: "rare",
            3: "legendary",
            4: "mythic",
        }
        rarity_tag = rarity_tags.get(rarity, "common")

        id_display = f"{hero['id']}".ljust(fixed_id_width)[:fixed_id_width]

        hero_info = (
            f"ID: {id_display} | Main Class: {main_class_name}, Sub Class: {sub_class_name}, "
            f"Gen: {hero.get('generation', 'Unknown')}, Summons: {hero['summonsRemaining']}"
        )

        abilities_info = {
            "A1": hero.get("active1", "Unknown"),
            "A2": hero.get("active2", "Unknown"),
            "P1": hero.get("passive1", "Unknown"),
            "P2": hero.get("passive2", "Unknown"),
        }

        realm_info = f" | Realm: {hero.get('network', 'Unknown')}"
        level = hero.get("level", "Unknown")
        profession = hero.get("professionStr", "Unknown Profession")

        return (
            hero_info,
            abilities_info,
            main_class_value,
            subclass_value,
            realm_info,
            rarity_tag,
            level,
            profession,
        )

    def bridge_heroes(self):
        password = self.password_entry.get()
        script_dir = os.getcwd()
        key_file_name = [f for f in os.listdir(script_dir) if f.endswith(".key")]
        if not key_file_name:
            self.async_log_to_ui("Key file not found.")
            return

        key_file_name = key_file_name[0]
        private_key = self.decrypt_key(
            os.path.join(script_dir, key_file_name), password
        )

        # Process each hero bridging in a sequence on a separate thread
        threading.Thread(
            target=self.process_all_bridges,
            args=(self.persistent_selected_heroes, private_key),
        ).start()

    def process_all_bridges(self, heroes, private_key):
        heroes_items = list(heroes.items())
        for hero_id, hero in heroes_items:
            self.process_bridge_hero(hero_id, hero, private_key)
            time.sleep(0.5)

    def process_bridge_hero(self, hero_id, hero, private_key):
        self.async_log_to_ui(f"Starting to bridge hero {hero_id}...")
        try:
            # Configuration for blockchain settings based on the network of the hero
            if hero["network"] == "kla":
                config_key = "serendale2"
                destination_chain_id = CONFIG["chain_ids"]["crystalvale"]
            elif hero["network"] == "dfk":
                config_key = "crystalvale"
                destination_chain_id = CONFIG["chain_ids"]["serendale2"]

            origin_realm_contract_address = CONFIG["contract_addresses"][config_key]
            rpc_address = CONFIG["rpc_addresses"][config_key]
            bridge_fee_in_wei = Web3.to_wei(CONFIG["fees_in_gwei"][config_key], "ether")

            w3 = Web3(Web3.HTTPProvider(rpc_address))
            account_address = w3.eth.account.from_key(private_key).address
            nonce = w3.eth.get_transaction_count(account_address)
            gas_price_gwei = {"maxFeePerGas": 26, "maxPriorityFeePerGas": 0}
            tx_timeout_seconds = 60

            # Send hero across the bridge
            tx_receipt = send_hero(
                origin_realm_contract_address,
                int(hero_id),
                destination_chain_id,
                bridge_fee_in_wei,
                private_key,
                nonce,
                gas_price_gwei,
                tx_timeout_seconds,
                rpc_address,
                self.async_log_to_ui,
            )

            # Update UI with the transaction result
            if tx_receipt:
                self.master.after(
                    0,
                    lambda: self.update_results_area(
                        {"action": "remove", "hero_id": hero_id}
                    ),
                )
            else:
                self.async_log_to_ui(f"Failed to bridge hero {hero_id}.")
        except Exception as e:
            self.async_log_to_ui(f"Error during bridging hero {hero_id}: {str(e)}")

    def decrypt_key(self, key_file_path, password_provided):
        try:
            with open(key_file_path, "rb") as f:
                salt = f.read(16)
                encrypted_key = f.read()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend(),
            )
            key = base64.urlsafe_b64encode(kdf.derive(password_provided.encode()))
            fernet = Fernet(key)
            decrypted_key = fernet.decrypt(encrypted_key).decode()
            return decrypted_key
        except Exception as e:
            self.async_log_to_ui(f"Error decrypting key: {e}")
            return None


def main():
    root = tk.Tk()
    app = HeroSearchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
