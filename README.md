# 📄 concilia-pdfs

Motor de conciliação automática de faturas de cartão entre:

- 📑 PDF do banco (BTG – multi-cartão no mesmo arquivo)
- 📱 PDFs do Organize (1 arquivo por cartão)

O sistema extrai, normaliza, reconcilia e gera relatórios Excel com os lançamentos faltantes ou divergentes.

---

# 🎯 Objetivo

Automatizar o processo manual de:

1. Copiar lançamentos do PDF do banco para Excel  
2. Copiar lançamentos do Organize  
3. Ajustar sinais  
4. Ordenar  
5. Comparar  
6. Identificar o que falta lançar  

Agora tudo é feito automaticamente por cartão.

---

# ⚙️ Como funciona

## 🔵 1. Leitura do PDF do Banco (BTG)

- Detecta automaticamente blocos por:
```

Lançamentos do cartão
Final XXXX

```
- Cada cartão é separado internamente.
- Detecta compras internacionais.
- Sempre usa o valor convertido em **R$** para conciliação.

---

## 🔵 2. Leitura dos PDFs do Organize

- 1 PDF por cartão.
- Detecta cartão pelo:
- Nome do arquivo (`final_1748.pdf`)
- Ou pelo texto interno do PDF.
- Inverte automaticamente o sinal dos valores (normalização).

---

## 🔵 3. Normalização Interna

Internamente o sistema usa padrão único:

- Débito → positivo  
- Crédito → negativo  
- Moeda → sempre BRL  
- Datas → `datetime`  
- Texto → sem acento / lower case  

---

## 🔵 4. Conciliação

### ✔ Match exato
- Mesma data  
- Mesmo valor (com tolerância de centavos)  
- Similaridade de descrição ≥ 90%  

### ⚠ Possível divergência
- Mesma data  
- Descrição parecida  
- Valor diferente  

### ❌ Faltando no Organize
- Existe no BTG  
- Não encontrado no Organize  

### ➕ Extra no Organize
- Existe no Organize  
- Não encontrado no BTG  

---

# 📁 Estrutura esperada do projeto

```

concilia-pdfs/
│
├── concilia_pdfs/
├── inputs/
│   ├── btg.pdf
│   └── organize_pdfs/
│       ├── final_1748.pdf
│       ├── final_5970.pdf
│
├── outputs/
├── requirements.txt
└── README.md

````

---

# 🚀 Instalação

## 1️⃣ Criar ambiente virtual

```bash
python -m venv .venv
````

## 2️⃣ Ativar

### Windows

```bash
.venv\Scripts\activate
```

### Mac / Linux

```bash
source .venv/bin/activate
```

## 3️⃣ Instalar dependências

```bash
pip install -r requirements.txt
```

---

# ▶️ Como executar

## Execução normal

```bash
python -m concilia_pdfs \
  --btg ./inputs/btg.pdf \
  --organize_dir ./inputs/organize_pdfs \
  --out ./outputs
```

## Execução com debug

```bash
python -m concilia_pdfs \
  --btg ./inputs/btg.pdf \
  --organize_dir ./inputs/organize_pdfs \
  --out ./outputs \
  --debug
```

---

# 📊 Saída

Para cada cartão detectado será gerado:

```
outputs/
  1748_conciliacao.xlsx
  5970_conciliacao.xlsx
```

Cada arquivo contém:

* `btg_normalizado`
* `organize_normalizado`
* `comparativo`
* `faltantes_no_organize`
* `extra_no_organize`
* `resumo`

---

# 🌎 Tratamento de Compras Internacionais

Quando existir:

```
Compra PEN 99,50
Cotação da moeda - R$ 1,70
Conversão para Real - R$ 169,65
```

O sistema:

* Usa apenas o valor convertido em **R$**
* Mantém metadados da moeda estrangeira
* Ignora o valor original em moeda estrangeira para conciliação

---

# 🔎 Regras de Sinal

| Fonte    | Débito | Crédito |
| -------- | ------ | ------- |
| BTG      | +      | -       |
| Organize | -      | +       |

Internamente o sistema normaliza para:

* Débito → positivo
* Crédito → negativo

---

# 🧠 Tecnologias Utilizadas

* Python 3.11+
* pdfplumber
* pandas
* openpyxl
* rapidfuzz
* pydantic
* decimal
* rich (logs)

---

# 🛠 Debug no VSCode

Configuração recomendada de `launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Concilia PDFs",
      "type": "python",
      "request": "launch",
      "module": "concilia_pdfs",
      "cwd": "${workspaceFolder}",
      "args": [
        "--btg",
        "${workspaceFolder}/inputs/btg.pdf",
        "--organize_dir",
        "${workspaceFolder}/inputs/organize_pdfs",
        "--out",
        "${workspaceFolder}/outputs",
        "--debug"
      ],
      "console": "integratedTerminal",
      "justMyCode": true,
      "stopOnEntry": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

---

# ⚠ Limitações atuais

* PDFs escaneados (imagem) não são suportados.
* Layouts diferentes de BTG/Organize podem exigir ajuste de regex.
* Ano da fatura depende da detecção correta no PDF.

---

# 🔮 Próximas Evoluções

* Exportar CSV pronto para importar no Organize
* Interface gráfica (Streamlit)
* Suporte a outros bancos
* Entrada via OFX
* Modo incremental (histórico de conciliações)

```

---
