# Image Remaster AI

Aplicativo em Python + Tkinter para:
- redimensionar imagens com alta qualidade;
- aplicar remasterização clássica;
- usar IA com Real-ESRGAN ncnn Vulkan;
- processar uma imagem ou várias de uma vez.

## Estrutura esperada do projeto

```text
image_remaster_ai_package/
├─ app.py
├─ requirements.txt
├─ requirements-build.txt
├─ run_windows.bat
├─ build_exe_windows.bat
├─ input/
├─ output/
└─ ai/
   └─ realesrgan/
      ├─ realesrgan-ncnn-vulkan.exe
      └─ models/
         ├─ realesrgan-x4plus.bin
         ├─ realesrgan-x4plus.param
         ├─ realesrnet-x4plus.bin
         ├─ realesrnet-x4plus.param
         ├─ realesrgan-x4plus-anime.bin
         ├─ realesrgan-x4plus-anime.param
         ├─ realesr-animevideov3.bin
         └─ realesr-animevideov3.param
```

---

## Passo a passo exato no Windows

### 1) Instale o Python
Instale o Python 64-bit. Durante a instalação, marque a opção para adicionar o Python ao PATH.

### 2) Baixe e extraia este projeto
Extraia a pasta inteira para um local simples, por exemplo:

```powershell
C:\Projetos\ImageRemasterAI
```

### 3) Abra o terminal dentro da pasta do projeto
No Explorer, entre na pasta do projeto, clique na barra de endereço, digite `powershell` e pressione Enter.

### 4) Crie o ambiente virtual
```powershell
py -3.12 -m venv .venv
```

### 5) Ative o ambiente virtual
```powershell
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação, rode isto na sessão atual:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

E depois ative novamente:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 6) Atualize o pip e instale as dependências
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 7) Teste se o Tkinter está funcionando
```powershell
python -m tkinter
```

Se abrir uma pequena janela do Tk, está tudo certo.

### 8) Baixe o Real-ESRGAN ncnn Vulkan
Baixe a release do **Real-ESRGAN-ncnn-vulkan** compatível com Windows x64.

Depois extraia o conteúdo para dentro desta pasta:

```text
ai\realesrgan\
```

Ao final, o executável e a pasta `models` devem ficar visíveis lá dentro.

### 9) Confira a estrutura final da IA
No PowerShell, rode:

```powershell
Get-ChildItem .\ai\realesrgan
Get-ChildItem .\ai\realesrgan\models
```

Você precisa ver:
- `realesrgan-ncnn-vulkan.exe`
- pasta `models`
- arquivos `.bin` e `.param`

### 10) Rode o aplicativo
```powershell
python .\app.py
```

---

## Uso dentro do aplicativo

### Fluxo recomendado
1. Clique em **Adicionar imagens** ou coloque os arquivos na pasta `input`.
2. Marque **Remaster clássica**.
3. Marque **IA Real-ESRGAN**.
4. Clique em **Auto detectar IA**.
5. Escolha o modelo.
6. Defina a resolução final.
7. Clique em **Processar**.

### Ordem do processamento
O app trabalha nesta ordem:
1. remasterização clássica;
2. IA;
3. resize final.

Isso evita subir a imagem com IA e depois perder o controle do tamanho final.

---

## Modelos de IA e quando usar

### `realesrgan-x4plus`
Use para fotos gerais e imagens do mundo real.

### `realesrnet-x4plus`
Use quando quiser um resultado mais conservador, com menos “inventação” de detalhe.

### `realesrgan-x4plus-anime`
Use para artes, ilustrações, personagens e imagens estilizadas.

### `realesr-animevideov3`
Use para anime/cartoon; também pode funcionar bem em algumas artes 2D simples.

---

## Configurações recomendadas

### Foto antiga ou comprimida
- Remaster clássica: ligada
- Auto contraste: ligado
- CLAHE: ligado
- Denoise: 4 a 8
- Nitidez: 80 a 120
- IA: `realesrgan-x4plus`
- Resize final: 1920x1080 ou 3840x2160

### Arte digital/anime
- Remaster clássica: ligada
- Denoise: 1 a 4
- Nitidez: 70 a 110
- IA: `realesrgan-x4plus-anime` ou `realesr-animevideov3`

### Só redimensionar sem IA
- Desmarque IA
- Deixe apenas Resize ligado
- Use preset 1080p, 1440p, 4K ou 8K

---

## Execução rápida por arquivo BAT

### Rodar
```cmd
run_windows.bat
```

### Gerar EXE
```cmd
build_exe_windows.bat
```

O executável final sairá na pasta:

```text
dist\ImageRemasterAI\
```

---

## Problemas comuns

### 1) A IA não é detectada
Confira se estes caminhos existem:

```powershell
Test-Path .\ai\realesrgan\realesrgan-ncnn-vulkan.exe
Test-Path .\ai\realesrgan\models
```

### 2) O modelo não foi encontrado
Confira se os arquivos `.param` e `.bin` do modelo escolhido estão dentro da pasta `models`.

### 3) O app abre, mas a IA falha
Tente:
- atualizar o driver da GPU;
- mudar o modelo;
- testar com `Tile = 0`;
- desativar IA e validar o modo clássico primeiro.

### 4) A imagem ficou artificial demais
Tente:
- usar `realesrnet-x4plus`;
- reduzir nitidez;
- reduzir denoise;
- fazer saída final em 1080p ou 1440p antes de tentar 4K.

---

## Como usar a pasta `input`
Você pode colocar várias imagens em:

```text
input\
```

Depois abrir o app e clicar em **Adicionar pasta input padrão**.

---

## Como empacotar com tudo dentro
Para distribuir para outro computador, copie a pasta gerada em:

```text
dist\ImageRemasterAI\
```

Junto com:
- a pasta `ai`;
- a pasta `models`;
- e, se quiser, algumas imagens de teste em `input`.

Se preferir, basta copiar o conteúdo completo do projeto já funcional para outra máquina e rodar por Python.
