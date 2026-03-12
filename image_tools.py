from __future__ import annotations

import os
import shlex
import subprocess
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
from PIL import Image, ImageOps

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
AI_MODELS = [
    "realesrgan-x4plus",
    "realesrnet-x4plus",
    "realesrgan-x4plus-anime",
    "realesr-animevideov3",
]


@dataclass
class ProcessingOptions:
    target_width: Optional[int]
    target_height: Optional[int]
    keep_aspect: bool
    do_resize: bool
    do_remaster: bool
    do_ai: bool
    autocontrast: bool
    denoise_strength: int
    sharpen_strength: int
    output_format: str
    suffix: str
    ai_exe: str
    ai_models_dir: str
    ai_model_name: str
    ai_scale: int
    ai_tile_size: int


class ImageRemasterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Remaster")
        self.root.geometry("1120x760")
        self.root.minsize(980, 700)

        self.file_paths: list[str] = []
        self.worker: Optional[threading.Thread] = None

        self._build_vars()
        self._build_ui()

    def _build_vars(self) -> None:
        self.output_dir_var = tk.StringVar(value=str(Path.cwd() / "output_images"))
        self.target_width_var = tk.StringVar(value="")
        self.target_height_var = tk.StringVar(value="")
        self.keep_aspect_var = tk.BooleanVar(value=True)
        self.do_resize_var = tk.BooleanVar(value=True)
        self.do_remaster_var = tk.BooleanVar(value=True)
        self.do_ai_var = tk.BooleanVar(value=False)
        self.autocontrast_var = tk.BooleanVar(value=True)
        self.denoise_var = tk.IntVar(value=4)
        self.sharpen_var = tk.IntVar(value=120)
        self.output_format_var = tk.StringVar(value="original")
        self.suffix_var = tk.StringVar(value="_rm")
        self.ai_exe_var = tk.StringVar(value="")
        self.ai_models_dir_var = tk.StringVar(value="")
        self.ai_model_var = tk.StringVar(value="realesrgan-x4plus")
        self.ai_scale_var = tk.StringVar(value="4")
        self.ai_tile_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Pronto")
        self.progress_var = tk.DoubleVar(value=0.0)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        top.pack(fill="both", expand=True)

        left = ttk.LabelFrame(top, text="Arquivos")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        left_buttons = ttk.Frame(left)
        left_buttons.pack(fill="x", padx=8, pady=8)
        ttk.Button(left_buttons, text="Adicionar imagens", command=self.add_files).pack(side="left")
        ttk.Button(left_buttons, text="Adicionar pasta", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(left_buttons, text="Remover selecionadas", command=self.remove_selected).pack(side="left")
        ttk.Button(left_buttons, text="Limpar", command=self.clear_files).pack(side="left", padx=6)

        self.listbox = tk.Listbox(left, selectmode=tk.EXTENDED)
        self.listbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        right = ttk.LabelFrame(top, text="Configurações")
        right.pack(side="left", fill="both", expand=True)

        cfg = ttk.Frame(right, padding=10)
        cfg.pack(fill="both", expand=True)
        cfg.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(cfg, text="Pasta de saída:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(cfg, textvariable=self.output_dir_var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(cfg, text="Procurar", command=self.choose_output_dir).grid(row=row, column=2, padx=(6, 0), pady=4)

        row += 1
        ops_frame = ttk.LabelFrame(cfg, text="Operações")
        ops_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Checkbutton(ops_frame, text="Resize", variable=self.do_resize_var).pack(side="left", padx=8, pady=6)
        ttk.Checkbutton(ops_frame, text="Remaster clássica", variable=self.do_remaster_var).pack(side="left", padx=8, pady=6)
        ttk.Checkbutton(ops_frame, text="IA Real-ESRGAN", variable=self.do_ai_var).pack(side="left", padx=8, pady=6)

        row += 1
        size_frame = ttk.LabelFrame(cfg, text="Tamanho final")
        size_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        size_frame.columnconfigure(1, weight=1)
        size_frame.columnconfigure(3, weight=1)
        ttk.Label(size_frame, text="Largura:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(size_frame, textvariable=self.target_width_var, width=12).grid(row=0, column=1, sticky="w", padx=(0, 8), pady=6)
        ttk.Label(size_frame, text="Altura:").grid(row=0, column=2, sticky="w", padx=8, pady=6)
        ttk.Entry(size_frame, textvariable=self.target_height_var, width=12).grid(row=0, column=3, sticky="w", padx=(0, 8), pady=6)
        ttk.Checkbutton(size_frame, text="Manter proporção", variable=self.keep_aspect_var).grid(row=0, column=4, sticky="w", padx=8, pady=6)

        row += 1
        remaster_frame = ttk.LabelFrame(cfg, text="Remaster clássica")
        remaster_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        remaster_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(remaster_frame, text="Auto contraste", variable=self.autocontrast_var).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Label(remaster_frame, text="Denoise:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Scale(remaster_frame, from_=0, to=20, orient="horizontal", variable=self.denoise_var).grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ttk.Label(remaster_frame, textvariable=self.denoise_var, width=4).grid(row=1, column=2, sticky="w")
        ttk.Label(remaster_frame, text="Nitidez:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ttk.Scale(remaster_frame, from_=0, to=250, orient="horizontal", variable=self.sharpen_var).grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        ttk.Label(remaster_frame, textvariable=self.sharpen_var, width=4).grid(row=2, column=2, sticky="w")

        row += 1
        ai_frame = ttk.LabelFrame(cfg, text="IA opcional - Real-ESRGAN externo")
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

        row += 1
        save_frame = ttk.LabelFrame(cfg, text="Saída")
        save_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Label(save_frame, text="Formato:").pack(side="left", padx=8, pady=6)
        ttk.Combobox(save_frame, textvariable=self.output_format_var, values=["original", "png", "jpg", "webp"], state="readonly", width=12).pack(side="left", pady=6)
        ttk.Label(save_frame, text="Sufixo:").pack(side="left", padx=(16, 8), pady=6)
        ttk.Entry(save_frame, textvariable=self.suffix_var, width=14).pack(side="left", pady=6)

        bottom = ttk.Frame(main)
        bottom.pack(fill="both", expand=False, pady=(8, 0))

        actions = ttk.Frame(bottom)
        actions.pack(fill="x")
        ttk.Button(actions, text="Processar", command=self.start_processing).pack(side="left")
        ttk.Button(actions, text="Abrir saída", command=self.open_output_dir).pack(side="left", padx=6)
        ttk.Label(actions, textvariable=self.status_var).pack(side="right")

        ttk.Progressbar(bottom, variable=self.progress_var, maximum=100).pack(fill="x", pady=8)

        log_frame = ttk.LabelFrame(bottom, text="Log")
        log_frame.pack(fill="both", expand=True)
        self.log = ScrolledText(log_frame, height=12, wrap="word")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.log.configure(state="disabled")

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
        paths: list[str] = []
        for ext in SUPPORTED_EXTS:
            paths.extend(str(p) for p in Path(folder).glob(f"*{ext}"))
            paths.extend(str(p) for p in Path(folder).glob(f"*{ext.upper()}"))
        self._add_paths(sorted(set(paths)))

    def _add_paths(self, paths: Iterable[str]) -> None:
        new_items = 0
        for path in paths:
            if path not in self.file_paths and Path(path).suffix.lower() in SUPPORTED_EXTS:
                self.file_paths.append(path)
                self.listbox.insert("end", path)
                new_items += 1
        if new_items:
            self.log_message(f"{new_items} arquivo(s) adicionados.")

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

    def open_output_dir(self) -> None:
        out = Path(self.output_dir_var.get().strip())
        out.mkdir(parents=True, exist_ok=True)
        os.startfile(out) if os.name == "nt" else subprocess.Popen(["xdg-open", str(out)])

    def collect_options(self) -> ProcessingOptions:
        width = self._parse_optional_int(self.target_width_var.get())
        height = self._parse_optional_int(self.target_height_var.get())
        if self.do_resize_var.get() and width is None and height is None:
            raise ValueError("Informe a largura, a altura, ou desmarque Resize.")

        ai_tile = self._parse_optional_int(self.ai_tile_var.get()) or 0
        ai_scale = int(self.ai_scale_var.get())

        return ProcessingOptions(
            target_width=width,
            target_height=height,
            keep_aspect=self.keep_aspect_var.get(),
            do_resize=self.do_resize_var.get(),
            do_remaster=self.do_remaster_var.get(),
            do_ai=self.do_ai_var.get(),
            autocontrast=self.autocontrast_var.get(),
            denoise_strength=int(self.denoise_var.get()),
            sharpen_strength=int(self.sharpen_var.get()),
            output_format=self.output_format_var.get(),
            suffix=self.suffix_var.get().strip(),
            ai_exe=self.ai_exe_var.get().strip(),
            ai_models_dir=self.ai_models_dir_var.get().strip(),
            ai_model_name=self.ai_model_var.get().strip(),
            ai_scale=ai_scale,
            ai_tile_size=ai_tile,
        )

    @staticmethod
    def _parse_optional_int(value: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        parsed = int(value)
        if parsed <= 0:
            raise ValueError("Largura, altura e tile devem ser maiores que zero.")
        return parsed

    def start_processing(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Em andamento", "Já existe um processamento em andamento.")
            return
        if not self.file_paths:
            messagebox.showwarning("Sem arquivos", "Adicione pelo menos uma imagem.")
            return
        try:
            options = self.collect_options()
        except Exception as exc:
            messagebox.showerror("Configuração inválida", str(exc))
            return

        self.worker = threading.Thread(target=self.process_all, args=(options,), daemon=True)
        self.worker.start()

    def process_all(self, options: ProcessingOptions) -> None:
        out_dir = Path(self.output_dir_var.get().strip())
        out_dir.mkdir(parents=True, exist_ok=True)

        if not options.do_resize and not options.do_remaster and not options.do_ai:
            self.log_message("Nada para fazer: marque pelo menos uma operação.")
            self.set_status("Nada para fazer")
            return

        if options.do_ai:
            if not options.ai_exe:
                self.log_message("IA marcada, mas o executável do Real-ESRGAN não foi informado.")
                self.set_status("Erro de configuração")
                return
            if not Path(options.ai_exe).exists():
                self.log_message("Executável do Real-ESRGAN não encontrado.")
                self.set_status("Erro de configuração")
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
                denoise_strength=options.denoise_strength,
                sharpen_strength=options.sharpen_strength,
            )

        if options.do_resize:
            image = resize_image(
                image,
                target_width=options.target_width,
                target_height=options.target_height,
                keep_aspect=options.keep_aspect,
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
            if options.do_resize and (options.target_width or options.target_height):
                image = resize_image(
                    image,
                    target_width=options.target_width,
                    target_height=options.target_height,
                    keep_aspect=options.keep_aspect,
                )

        suffix = options.suffix
        ext = choose_output_extension(src, options.output_format, image.mode)
        out_name = f"{src.stem}{suffix}{ext}"
        out_path = out_dir / out_name
        save_image(image, out_path, options.output_format)
        return out_path


def load_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        return img.copy()


def resize_image(image: Image.Image, target_width: Optional[int], target_height: Optional[int], keep_aspect: bool) -> Image.Image:
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

    if new_size == image.size:
        return image
    return image.resize(new_size, Image.Resampling.LANCZOS)


def remaster_classic(
    image: Image.Image,
    autocontrast: bool = True,
    denoise_strength: int = 4,
    sharpen_strength: int = 120,
) -> Image.Image:
    has_alpha = image.mode == "RGBA"
    alpha = None
    working = image

    if autocontrast:
        if has_alpha:
            rgb = Image.new("RGB", image.size, (0, 0, 0))
            rgb.paste(image, mask=image.getchannel("A"))
            working = ImageOps.autocontrast(rgb)
            alpha = image.getchannel("A")
        else:
            working = ImageOps.autocontrast(working)

    if has_alpha and alpha is None:
        alpha = image.getchannel("A")
        working = image.convert("RGB")

    np_img = np.array(working.convert("RGB"))
    bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)

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

        cmd = [str(exe), "-i", str(in_path), "-o", str(out_path), "-n", model_name, "-s", str(scale), "-f", "png"]
        if models_dir:
            cmd.extend(["-m", models_dir])
        if tile_size >= 0:
            cmd.extend(["-t", str(tile_size)])

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

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


def choose_output_extension(src: Path, output_format: str, image_mode: str) -> str:
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


def save_image(image: Image.Image, out_path: Path, output_format: str) -> None:
    ext = out_path.suffix.lower()
    fmt = "PNG"
    params: dict[str, object] = {}

    if ext in {".jpg", ".jpeg"}:
        fmt = "JPEG"
        params = {"quality": 95, "subsampling": 0, "optimize": True}
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
    elif ext == ".webp":
        fmt = "WEBP"
        params = {"quality": 95, "lossless": True}
    else:
        fmt = "PNG"
        params = {"compress_level": 2}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format=fmt, **params)


def main() -> None:
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except Exception:
        pass
    app = ImageRemasterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
