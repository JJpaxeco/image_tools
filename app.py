from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

APP_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = APP_DIR / "input"
DEFAULT_OUTPUT_DIR = APP_DIR / "output"
DEFAULT_AI_DIR = APP_DIR / "ai" / "realesrgan"

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
AI_MODELS = [
    "realesrgan-x4plus",
    "realesrnet-x4plus",
    "realesrgan-x4plus-anime",
    "realesr-animevideov3",
]
RESOLUTION_PRESETS = {
    "Sem preset": (None, None),
    "HD 1280x720": (1280, 720),
    "Full HD 1920x1080": (1920, 1080),
    "Quad HD 2560x1440": (2560, 1440),
    "4K UHD 3840x2160": (3840, 2160),
    "8K UHD 7680x4320": (7680, 4320),
}


@dataclass
class ProcessingOptions:
    do_resize: bool
    target_width: Optional[int]
    target_height: Optional[int]
    keep_aspect: bool
    fill_background: bool
    background_color: str
    do_remaster: bool
    autocontrast: bool
    clahe: bool
    denoise_strength: int
    sharpen_strength: int
    color_boost: int
    do_ai: bool
    ai_exe: str
    ai_models_dir: str
    ai_model_name: str
    ai_scale: int
    ai_tile_size: int
    output_format: str
    suffix: str
    jpeg_quality: int


class ImageRemasterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Remaster AI")
        self.root.geometry("1260x860")
        self.root.minsize(1100, 760)

        self.file_paths: list[str] = []
        self.worker: Optional[threading.Thread] = None

        self._build_vars()
        self._build_ui()
        self._autofill_default_paths()

    def _build_vars(self) -> None:
        self.output_dir_var = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.preset_var = tk.StringVar(value="Sem preset")
        self.target_width_var = tk.StringVar(value="")
        self.target_height_var = tk.StringVar(value="")
        self.keep_aspect_var = tk.BooleanVar(value=True)
        self.fill_background_var = tk.BooleanVar(value=False)
        self.background_color_var = tk.StringVar(value="#000000")

        self.do_resize_var = tk.BooleanVar(value=True)
        self.do_remaster_var = tk.BooleanVar(value=True)
        self.do_ai_var = tk.BooleanVar(value=False)

        self.autocontrast_var = tk.BooleanVar(value=True)
        self.clahe_var = tk.BooleanVar(value=True)
        self.denoise_var = tk.IntVar(value=4)
        self.sharpen_var = tk.IntVar(value=110)
        self.color_boost_var = tk.IntVar(value=0)

        self.ai_exe_var = tk.StringVar(value="")
        self.ai_models_dir_var = tk.StringVar(value="")
        self.ai_model_var = tk.StringVar(value="realesrgan-x4plus")
        self.ai_scale_var = tk.StringVar(value="4")
        self.ai_tile_var = tk.StringVar(value="0")

        self.output_format_var = tk.StringVar(value="png")
        self.suffix_var = tk.StringVar(value="_rm")
        self.jpeg_quality_var = tk.IntVar(value=95)

        self.status_var = tk.StringVar(value="Pronto")
        self.progress_var = tk.DoubleVar(value=0.0)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        top = ttk.PanedWindow(main, orient="horizontal")
        top.pack(fill="both", expand=True)

        left = ttk.Frame(top)
        right = ttk.Frame(top)
        top.add(left, weight=1)
        top.add(right, weight=2)

        self._build_left_panel(left)
        self._build_right_panel(right)
        self._build_bottom(main)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        files_frame = ttk.LabelFrame(parent, text="Arquivos")
        files_frame.pack(fill="both", expand=True)

        buttons = ttk.Frame(files_frame)
        buttons.pack(fill="x", padx=8, pady=8)
        ttk.Button(buttons, text="Adicionar imagens", command=self.add_files).pack(side="left")
        ttk.Button(buttons, text="Adicionar pasta", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(buttons, text="Remover", command=self.remove_selected).pack(side="left")
        ttk.Button(buttons, text="Limpar", command=self.clear_files).pack(side="left", padx=6)

        hint = ttk.Label(
            files_frame,
            text="Dica: você pode processar uma pasta inteira. Formatos: PNG, JPG, WEBP, BMP, TIF/TIFF.",
            wraplength=320,
            justify="left",
        )
        hint.pack(fill="x", padx=8, pady=(0, 8))

        self.listbox = tk.Listbox(files_frame, selectmode=tk.EXTENDED)
        self.listbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        cfg = ttk.Frame(scrollable, padding=(0, 0, 10, 0))
        cfg.pack(fill="both", expand=True)
        cfg.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(cfg, text="Pasta de saída:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(cfg, textvariable=self.output_dir_var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(cfg, text="Procurar", command=self.choose_output_dir).grid(row=row, column=2, padx=(6, 0), pady=4)

        row += 1
        ops_frame = ttk.LabelFrame(cfg, text="Operações")
        ops_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Checkbutton(ops_frame, text="Redimensionar", variable=self.do_resize_var).pack(side="left", padx=8, pady=6)
        ttk.Checkbutton(ops_frame, text="Remaster clássica", variable=self.do_remaster_var).pack(side="left", padx=8, pady=6)
        ttk.Checkbutton(ops_frame, text="IA Real-ESRGAN", variable=self.do_ai_var).pack(side="left", padx=8, pady=6)

        row += 1
        size_frame = ttk.LabelFrame(cfg, text="Resolução final")
        size_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        for col in range(5):
            size_frame.columnconfigure(col, weight=1 if col in (1, 3) else 0)

        ttk.Label(size_frame, text="Preset:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        preset_combo = ttk.Combobox(size_frame, textvariable=self.preset_var, values=list(RESOLUTION_PRESETS.keys()), state="readonly")
        preset_combo.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=6)
        preset_combo.bind("<<ComboboxSelected>>", self.apply_preset)
        ttk.Button(size_frame, text="Aplicar", command=self.apply_preset).grid(row=0, column=4, sticky="w", padx=(0, 8), pady=6)

        ttk.Label(size_frame, text="Largura:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(size_frame, textvariable=self.target_width_var, width=12).grid(row=1, column=1, sticky="w", padx=(0, 8), pady=6)
        ttk.Label(size_frame, text="Altura:").grid(row=1, column=2, sticky="w", padx=8, pady=6)
        ttk.Entry(size_frame, textvariable=self.target_height_var, width=12).grid(row=1, column=3, sticky="w", padx=(0, 8), pady=6)
        ttk.Checkbutton(size_frame, text="Manter proporção", variable=self.keep_aspect_var).grid(row=1, column=4, sticky="w", padx=8, pady=6)

        ttk.Checkbutton(size_frame, text="Preencher área vazia com fundo", variable=self.fill_background_var).grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=6)
        ttk.Label(size_frame, text="Cor do fundo:").grid(row=2, column=2, sticky="e", padx=8, pady=6)
        ttk.Entry(size_frame, textvariable=self.background_color_var, width=12).grid(row=2, column=3, sticky="w", padx=(0, 8), pady=6)

        row += 1
        remaster_frame = ttk.LabelFrame(cfg, text="Remaster clássica")
        remaster_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        remaster_frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(remaster_frame, text="Auto contraste", variable=self.autocontrast_var).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Checkbutton(remaster_frame, text="CLAHE (microcontraste)", variable=self.clahe_var).grid(row=0, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(remaster_frame, text="Denoise:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Scale(remaster_frame, from_=0, to=20, orient="horizontal", variable=self.denoise_var).grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ttk.Label(remaster_frame, textvariable=self.denoise_var, width=4).grid(row=1, column=2, sticky="w")

        ttk.Label(remaster_frame, text="Nitidez:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ttk.Scale(remaster_frame, from_=0, to=250, orient="horizontal", variable=self.sharpen_var).grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        ttk.Label(remaster_frame, textvariable=self.sharpen_var, width=4).grid(row=2, column=2, sticky="w")

        ttk.Label(remaster_frame, text="Cor/Vibrância:").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ttk.Scale(remaster_frame, from_=-30, to=50, orient="horizontal", variable=self.color_boost_var).grid(row=3, column=1, sticky="ew", padx=8, pady=6)
        ttk.Label(remaster_frame, textvariable=self.color_boost_var, width=4).grid(row=3, column=2, sticky="w")

        row += 1
        ai_frame = ttk.LabelFrame(cfg, text="IA - Real-ESRGAN ncnn Vulkan")
        ai_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        ai_frame.columnconfigure(1, weight=1)

        ttk.Label(ai_frame, text="Executável:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(ai_frame, textvariable=self.ai_exe_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(ai_frame, text="Procurar", command=self.choose_ai_exe).grid(row=0, column=2, padx=(6, 0), pady=4)

        ttk.Label(ai_frame, text="Pasta models:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(ai_frame, textvariable=self.ai_models_dir_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(ai_frame, text="Procurar", command=self.choose_ai_models_dir).grid(row=1, column=2, padx=(6, 0), pady=4)

        ttk.Label(ai_frame, text="Modelo:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(ai_frame, textvariable=self.ai_model_var, values=AI_MODELS, state="readonly").grid(row=2, column=1, sticky="w", pady=4)

        small = ttk.Frame(ai_frame)
        small.grid(row=3, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        ttk.Label(small, text="Escala IA:").pack(side="left")
        ttk.Combobox(small, textvariable=self.ai_scale_var, values=["2", "3", "4"], width=6, state="readonly").pack(side="left", padx=(6, 12))
        ttk.Label(small, text="Tile:").pack(side="left")
        ttk.Entry(small, textvariable=self.ai_tile_var, width=8).pack(side="left", padx=(6, 12))
        ttk.Label(small, text="0 = automático").pack(side="left")
        ttk.Button(small, text="Auto detectar IA", command=self.autodetect_ai).pack(side="left", padx=(18, 0))
        ttk.Button(small, text="Testar IA", command=self.test_ai_configuration).pack(side="left", padx=(6, 0))

        info = ttk.Label(
            ai_frame,
            text="Ordem do pipeline: remaster clássica -> IA -> resize final. Se o alvo final for menor que a saída da IA, o app faz o ajuste no final.",
            wraplength=720,
            justify="left",
        )
        info.grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(4, 8))

        row += 1
        save_frame = ttk.LabelFrame(cfg, text="Saída")
        save_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Label(save_frame, text="Formato:").pack(side="left", padx=8, pady=6)
        ttk.Combobox(save_frame, textvariable=self.output_format_var, values=["original", "png", "jpg", "webp"], state="readonly", width=12).pack(side="left", pady=6)
        ttk.Label(save_frame, text="Sufixo:").pack(side="left", padx=(16, 8), pady=6)
        ttk.Entry(save_frame, textvariable=self.suffix_var, width=14).pack(side="left", pady=6)
        ttk.Label(save_frame, text="Qualidade JPG:").pack(side="left", padx=(16, 8), pady=6)
        ttk.Scale(save_frame, from_=80, to=100, orient="horizontal", variable=self.jpeg_quality_var).pack(side="left", pady=6)
        ttk.Label(save_frame, textvariable=self.jpeg_quality_var, width=4).pack(side="left", pady=6)

    def _build_bottom(self, parent: ttk.Frame) -> None:
        bottom = ttk.Frame(parent)
        bottom.pack(fill="both", expand=False, pady=(8, 0))

        actions = ttk.Frame(bottom)
        actions.pack(fill="x")
        ttk.Button(actions, text="Processar", command=self.start_processing).pack(side="left")
        ttk.Button(actions, text="Abrir saída", command=self.open_output_dir).pack(side="left", padx=6)
        ttk.Button(actions, text="Adicionar pasta input padrão", command=self.add_default_input_dir).pack(side="left", padx=6)
        ttk.Label(actions, textvariable=self.status_var).pack(side="right")

        ttk.Progressbar(bottom, variable=self.progress_var, maximum=100).pack(fill="x", pady=8)

        log_frame = ttk.LabelFrame(bottom, text="Log")
        log_frame.pack(fill="both", expand=True)
        self.log = ScrolledText(log_frame, height=14, wrap="word")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.log.configure(state="disabled")

    def _autofill_default_paths(self) -> None:
        self.autodetect_ai(silent=True)
        DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def log_message(self, message: str) -> None:
        def _append() -> None:
            self.log.configure(state="normal")
            self.log.insert("end", message.rstrip() + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")

        self.root.after(0, _append)

    def set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(text))

    def set_progress(self, value: float) -> None:
        self.root.after(0, lambda: self.progress_var.set(value))

    def apply_preset(self, event: object | None = None) -> None:
        width, height = RESOLUTION_PRESETS.get(self.preset_var.get(), (None, None))
        self.target_width_var.set("" if width is None else str(width))
        self.target_height_var.set("" if height is None else str(height))

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Selecione imagens",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff")],
        )
        self._add_paths(paths)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecione uma pasta")
        if not folder:
            return
        self._add_paths(self._scan_folder(Path(folder)))

    def add_default_input_dir(self) -> None:
        DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._add_paths(self._scan_folder(DEFAULT_INPUT_DIR))

    def _scan_folder(self, folder: Path) -> list[str]:
        paths: list[str] = []
        for item in folder.iterdir():
            if item.is_file() and item.suffix.lower() in SUPPORTED_EXTS:
                paths.append(str(item))
        return sorted(paths)

    def _add_paths(self, paths: Iterable[str]) -> None:
        new_items = 0
        for path in paths:
            if path not in self.file_paths and Path(path).suffix.lower() in SUPPORTED_EXTS:
                self.file_paths.append(path)
                self.listbox.insert("end", path)
                new_items += 1
        if new_items:
            self.log_message(f"{new_items} arquivo(s) adicionados.")
        else:
            self.log_message("Nenhum arquivo novo foi adicionado.")

    def remove_selected(self) -> None:
        selected = list(self.listbox.curselection())
        if not selected:
            return
        for index in reversed(selected):
            self.file_paths.pop(index)
            self.listbox.delete(index)
        self.log_message(f"{len(selected)} arquivo(s) removidos.")

    def clear_files(self) -> None:
        self.file_paths.clear()
        self.listbox.delete(0, "end")
        self.log_message("Lista de arquivos limpa.")

    def choose_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="Escolha a pasta de saída")
        if folder:
            self.output_dir_var.set(folder)

    def choose_ai_exe(self) -> None:
        path = filedialog.askopenfilename(title="Escolha o executável do Real-ESRGAN")
        if path:
            self.ai_exe_var.set(path)

    def choose_ai_models_dir(self) -> None:
        folder = filedialog.askdirectory(title="Escolha a pasta models")
        if folder:
            self.ai_models_dir_var.set(folder)

    def autodetect_ai(self, silent: bool = False) -> None:
        possible_exes = []
        if os.name == "nt":
            possible_exes.extend([
                DEFAULT_AI_DIR / "realesrgan-ncnn-vulkan.exe",
                DEFAULT_AI_DIR / "realesrgan-ncnn-vulkan-20220424-windows" / "realesrgan-ncnn-vulkan.exe",
            ])
        else:
            possible_exes.extend([
                DEFAULT_AI_DIR / "realesrgan-ncnn-vulkan",
                DEFAULT_AI_DIR / "realesrgan-ncnn-vulkan-20220424-ubuntu" / "realesrgan-ncnn-vulkan",
            ])

        found_exe = next((p for p in possible_exes if p.exists()), None)
        found_models = next((p for p in [DEFAULT_AI_DIR / "models", DEFAULT_AI_DIR / "realesrgan-ncnn-vulkan-20220424-windows" / "models", DEFAULT_AI_DIR / "realesrgan-ncnn-vulkan-20220424-ubuntu" / "models"] if p.exists()), None)

        if found_exe:
            self.ai_exe_var.set(str(found_exe))
        if found_models:
            self.ai_models_dir_var.set(str(found_models))

        if not silent:
            if found_exe and found_models:
                self.log_message("IA detectada automaticamente.")
            else:
                self.log_message("IA não detectada automaticamente. Preencha os campos manualmente ou siga o README.")

    def open_output_dir(self) -> None:
        out = Path(self.output_dir_var.get().strip() or DEFAULT_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(out)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(out)])
        else:
            subprocess.Popen(["xdg-open", str(out)])

    def collect_options(self) -> ProcessingOptions:
        width = self._parse_optional_int(self.target_width_var.get())
        height = self._parse_optional_int(self.target_height_var.get())
        if self.do_resize_var.get() and width is None and height is None:
            raise ValueError("Informe largura e/ou altura, ou desmarque Redimensionar.")

        ai_tile = self._parse_optional_int_allow_zero(self.ai_tile_var.get())
        ai_scale = int(self.ai_scale_var.get())
        background_color = self.background_color_var.get().strip() or "#000000"

        return ProcessingOptions(
            do_resize=self.do_resize_var.get(),
            target_width=width,
            target_height=height,
            keep_aspect=self.keep_aspect_var.get(),
            fill_background=self.fill_background_var.get(),
            background_color=background_color,
            do_remaster=self.do_remaster_var.get(),
            autocontrast=self.autocontrast_var.get(),
            clahe=self.clahe_var.get(),
            denoise_strength=int(self.denoise_var.get()),
            sharpen_strength=int(self.sharpen_var.get()),
            color_boost=int(self.color_boost_var.get()),
            do_ai=self.do_ai_var.get(),
            ai_exe=self.ai_exe_var.get().strip(),
            ai_models_dir=self.ai_models_dir_var.get().strip(),
            ai_model_name=self.ai_model_var.get().strip(),
            ai_scale=ai_scale,
            ai_tile_size=ai_tile,
            output_format=self.output_format_var.get(),
            suffix=self.suffix_var.get().strip(),
            jpeg_quality=int(self.jpeg_quality_var.get()),
        )

    @staticmethod
    def _parse_optional_int(value: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        parsed = int(value)
        if parsed <= 0:
            raise ValueError("Largura e altura devem ser maiores que zero.")
        return parsed

    @staticmethod
    def _parse_optional_int_allow_zero(value: str) -> int:
        value = value.strip()
        if not value:
            return 0
        parsed = int(value)
        if parsed < 0:
            raise ValueError("Tile deve ser zero ou maior.")
        return parsed

    def test_ai_configuration(self) -> None:
        try:
            opts = self.collect_options()
            validate_ai(opts.ai_exe, opts.ai_models_dir, opts.ai_model_name)
        except Exception as exc:
            messagebox.showerror("IA", str(exc))
            return
        messagebox.showinfo("IA", "Configuração da IA parece válida.")

    def start_processing(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Em andamento", "Já existe um processamento em andamento.")
            return
        if not self.file_paths:
            messagebox.showwarning("Sem arquivos", "Adicione pelo menos uma imagem.")
            return
        try:
            options = self.collect_options()
            if options.do_ai:
                validate_ai(options.ai_exe, options.ai_models_dir, options.ai_model_name)
        except Exception as exc:
            messagebox.showerror("Configuração inválida", str(exc))
            return

        self.worker = threading.Thread(target=self.process_all, args=(options,), daemon=True)
        self.worker.start()

    def process_all(self, options: ProcessingOptions) -> None:
        out_dir = Path(self.output_dir_var.get().strip() or DEFAULT_OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        if not options.do_resize and not options.do_remaster and not options.do_ai:
            self.log_message("Nada para fazer: marque pelo menos uma operação.")
            self.set_status("Nada para fazer")
            return

        total = len(self.file_paths)
        success = 0
        self.set_progress(0)
        self.set_status("Processando...")

        for index, path in enumerate(self.file_paths, start=1):
            src = Path(path)
            self.log_message(f"[{index}/{total}] {src.name}")
            try:
                result = self.process_single(src, out_dir, options)
                success += 1
                self.log_message(f"  OK -> {result.name}")
            except Exception as exc:
                self.log_message(f"  ERRO -> {exc}")
            self.set_progress(index / total * 100)

        self.set_status(f"Concluído: {success}/{total}")
        self.log_message(f"Finalizado. Sucesso: {success}/{total}.")

    def process_single(self, src: Path, out_dir: Path, options: ProcessingOptions) -> Path:
        image = load_image(src)

        if options.do_remaster:
            image = remaster_classic(
                image,
                autocontrast=options.autocontrast,
                clahe=options.clahe,
                denoise_strength=options.denoise_strength,
                sharpen_strength=options.sharpen_strength,
                color_boost=options.color_boost,
            )

        if options.do_ai:
            image = upscale_with_realesrgan(
                image=image,
                exe_path=options.ai_exe,
                models_dir=options.ai_models_dir,
                model_name=options.ai_model_name,
                scale=options.ai_scale,
                tile_size=options.ai_tile_size,
            )

        if options.do_resize:
            image = resize_image(
                image,
                target_width=options.target_width,
                target_height=options.target_height,
                keep_aspect=options.keep_aspect,
                fill_background=options.fill_background,
                background_color=options.background_color,
            )

        ext = choose_output_extension(src, options.output_format)
        out_name = f"{src.stem}{options.suffix}{ext}"
        out_path = out_dir / out_name
        save_image(image, out_path, options.output_format, options.jpeg_quality)
        return out_path


def validate_ai(exe_path: str, models_dir: str, model_name: str) -> None:
    exe = Path(exe_path)
    if not exe_path:
        raise ValueError("A IA está marcada, mas o executável do Real-ESRGAN não foi informado.")
    if not exe.exists():
        raise FileNotFoundError("Executável do Real-ESRGAN não encontrado.")

    models = Path(models_dir)
    if not models_dir:
        raise ValueError("A IA está marcada, mas a pasta models não foi informada.")
    if not models.exists():
        raise FileNotFoundError("Pasta models não encontrada.")

    param_file = models / f"{model_name}.param"
    bin_file = models / f"{model_name}.bin"
    if not param_file.exists() or not bin_file.exists():
        raise FileNotFoundError(
            f"Modelo '{model_name}' não encontrado na pasta models. Esperado: {param_file.name} e {bin_file.name}."
        )


def load_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        return img.copy()


def resize_image(
    image: Image.Image,
    target_width: Optional[int],
    target_height: Optional[int],
    keep_aspect: bool,
    fill_background: bool,
    background_color: str,
) -> Image.Image:
    src_w, src_h = image.size

    if target_width is None and target_height is None:
        return image

    if keep_aspect:
        if target_width and target_height:
            scale = min(target_width / src_w, target_height / src_h)
            new_size = (max(1, round(src_w * scale)), max(1, round(src_h * scale)))
        elif target_width:
            new_h = max(1, round(src_h * (target_width / src_w)))
            new_size = (target_width, new_h)
        else:
            new_w = max(1, round(src_w * (target_height / src_h)))
            new_size = (new_w, target_height or src_h)
    else:
        new_size = (target_width or src_w, target_height or src_h)

    if new_size == image.size and not (fill_background and target_width and target_height):
        return image

    resized = image.resize(new_size, Image.Resampling.LANCZOS)

    if fill_background and target_width and target_height and keep_aspect:
        mode = "RGBA" if resized.mode == "RGBA" else "RGB"
        bg = Image.new(mode, (target_width, target_height), background_color)
        offset = ((target_width - resized.width) // 2, (target_height - resized.height) // 2)
        if resized.mode == "RGBA":
            bg.paste(resized, offset, resized)
        else:
            bg.paste(resized, offset)
        return bg

    return resized


def remaster_classic(
    image: Image.Image,
    autocontrast: bool = True,
    clahe: bool = True,
    denoise_strength: int = 4,
    sharpen_strength: int = 110,
    color_boost: int = 0,
) -> Image.Image:
    has_alpha = image.mode == "RGBA"
    alpha = image.getchannel("A") if has_alpha else None
    working = image.convert("RGB")

    if autocontrast:
        working = ImageOps.autocontrast(working)

    if color_boost != 0:
        enhancer = ImageEnhance.Color(working)
        working = enhancer.enhance(max(0.1, 1.0 + (color_boost / 100.0)))

    np_img = np.array(working)
    bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)

    if clahe:
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe_filter = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l2 = clahe_filter.apply(l)
        lab = cv2.merge((l2, a, b))
        bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    if denoise_strength > 0:
        h = max(1, denoise_strength)
        bgr = cv2.fastNlMeansDenoisingColored(bgr, None, h, h, 7, 21)

    if sharpen_strength > 0:
        amount = sharpen_strength / 100.0
        blurred = cv2.GaussianBlur(bgr, (0, 0), sigmaX=1.2)
        bgr = cv2.addWeighted(bgr, 1.0 + amount, blurred, -amount, 0)

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    out = Image.fromarray(rgb)
    if has_alpha and alpha is not None:
        out.putalpha(alpha)
    return out


def upscale_with_realesrgan(
    image: Image.Image,
    exe_path: str,
    models_dir: str,
    model_name: str,
    scale: int,
    tile_size: int,
) -> Image.Image:
    exe = Path(exe_path)
    if not exe.exists():
        raise FileNotFoundError("Executável do Real-ESRGAN não encontrado.")

    with tempfile.TemporaryDirectory(prefix="img_rm_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        in_path = tmpdir_path / "input.png"
        out_path = tmpdir_path / "output.png"
        image.save(in_path, format="PNG")

        cmd = [
            str(exe),
            "-i", str(in_path),
            "-o", str(out_path),
            "-n", model_name,
            "-s", str(scale),
            "-f", "png",
        ]
        if models_dir:
            cmd.extend(["-m", models_dir])
        if tile_size >= 0:
            cmd.extend(["-t", str(tile_size)])

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
            check=False,
        )

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"Falha no Real-ESRGAN: {stderr or 'retorno não zero'}")

        if not out_path.exists():
            raise RuntimeError("O Real-ESRGAN terminou sem gerar o arquivo de saída.")

        return load_image(out_path)


def choose_output_extension(src: Path, output_format: str) -> str:
    if output_format == "original":
        ext = src.suffix.lower()
        return ".png" if ext not in SUPPORTED_EXTS else ext
    if output_format == "jpg":
        return ".jpg"
    if output_format == "png":
        return ".png"
    if output_format == "webp":
        return ".webp"
    return ".png"


def save_image(image: Image.Image, out_path: Path, output_format: str, jpeg_quality: int) -> None:
    ext = out_path.suffix.lower()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if ext in {".jpg", ".jpeg"}:
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        image.save(out_path, format="JPEG", quality=jpeg_quality, subsampling=0, optimize=True)
        return

    if ext == ".webp":
        image.save(out_path, format="WEBP", quality=jpeg_quality, method=6)
        return

    image.save(out_path, format="PNG", compress_level=2)


def main() -> None:
    DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    style = ttk.Style(root)
    for theme in ("vista", "clam", "default"):
        try:
            style.theme_use(theme)
            break
        except Exception:
            continue
    app = ImageRemasterApp(root)
    app.log_message("Projeto carregado.")
    app.log_message(f"Pasta input padrão: {DEFAULT_INPUT_DIR}")
    app.log_message(f"Pasta output padrão: {DEFAULT_OUTPUT_DIR}")
    root.mainloop()


if __name__ == "__main__":
    main()
