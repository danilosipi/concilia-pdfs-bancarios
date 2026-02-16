import re
import pdfplumber
from typing import Iterator, Optional
import logging
from pathlib import Path

from concilia_pdfs.core.models import Transaction, Source
from concilia_pdfs.utils.normalization import normalize_text, parse_brl_value, parse_date

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CARD_FINAL_FROM_FILENAME_RE = re.compile(r"final_(\d{4})", re.IGNORECASE)
CARD_FINAL_FROM_TEXT_RE = re.compile(r"Final\s+(\d{4})")

# Fallback: "DD/MM/YYYY Descricao -99,90"
ORGANIZE_TEXT_RE = re.compile(
    r"(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+(-?[\d.,]+)$"
)

def _detect_card_final(filename: str, full_text: str) -> Optional[str]:
    m = CARD_FINAL_FROM_FILENAME_RE.search(filename)
    if m:
        return m.group(1)
    m = CARD_FINAL_FROM_TEXT_RE.search(full_text)
    if m:
        return m.group(1)
    return None

def _create_transaction(card_final: str, date_str: str, desc_raw: str, amount_str: str, raw_lines: list[str]) -> Optional[Transaction]:
    tx_date = parse_date(date_str)
    amount = parse_brl_value(amount_str)
    if tx_date is None or amount is None:
        return None

    # Regra: Organize vem com sinal invertido em relação ao BTG -> normalizar invertendo
    amount *= -1

    return Transaction(
        card_final=card_final,
        source=Source.ORGANIZE,
        tx_date=tx_date,
        description_raw=desc_raw.strip(),
        description_norm=normalize_text(desc_raw),
        amount=amount,
        raw_lines=raw_lines,
    )

def parse_organize_pdf(pdf_path: str) -> Iterator[Transaction]:
    """
    Parseia um PDF do Organize (1 PDF por cartão) e retorna Transactions normalizadas.
    Evita duplicação: fallback por texto é processado por página.
    """
    logging.info(f"Iniciando análise do PDF do Organize: {pdf_path}")
    filename = Path(pdf_path).name

    with pdfplumber.open(pdf_path) as pdf:
        # Texto completo (apenas para detectar final do cartão)
        full_text = "\n".join((page.extract_text() or "") for page in pdf.pages)

        card_final = _detect_card_final(filename, full_text)
        if not card_final:
            logging.error(f"Não foi possível determinar o final do cartão pelo nome do arquivo ou texto para '{filename}'. Pulando.")
            return

        all_transactions: list[Transaction] = []

        for page in pdf.pages:
            # 1) Tenta tabelas
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    # Heurística: primeira linha pode ser header
                    for row in table[1:]:
                        if not row or len(row) < 2:
                            continue

                        # data geralmente na primeira coluna
                        date_cell = (row[0] or "").strip()
                        if not date_cell:
                            continue

                        # valor: em muitos PDFs do Organize, é a última célula preenchida
                        amount_cell = None
                        for cell in reversed(row):
                            if cell is not None and str(cell).strip():
                                amount_cell = str(cell).strip()
                                break
                        if not amount_cell:
                            continue

                        # descrição: geralmente na segunda coluna
                        desc_cell = (row[1] or "").strip()
                        if not desc_cell:
                            continue

                        tx = _create_transaction(card_final, date_cell, desc_cell, amount_cell, [str(row)])
                        if tx:
                            all_transactions.append(tx)

                continue  # próxima página

            # 2) Fallback: texto por página (NÃO usar full_text para cada página)
            page_text = page.extract_text() or ""
            for line in page_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                m = ORGANIZE_TEXT_RE.match(line)
                if not m:
                    continue
                date_str, desc_raw, amount_str = m.groups()
                tx = _create_transaction(card_final, date_str, desc_raw, amount_str, [line])
                if tx:
                    all_transactions.append(tx)

    logging.info(f"Finalizada a análise do PDF do Organize: {pdf_path}, encontradas {len(all_transactions)} transações.")
    yield from all_transactions
