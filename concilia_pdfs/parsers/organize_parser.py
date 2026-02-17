# concilia_pdfs/parsers/organize_parser.py
import re
from typing import Iterator, Optional
import logging
from pathlib import Path

from concilia_pdfs.core.models import Transaction, Source
from concilia_pdfs.utils.normalization import normalize_text, parse_brl_value, parse_date
from concilia_pdfs.utils.pdf_open import open_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

CARD_FINAL_FROM_FILENAME_RE = re.compile(r"final_(\d{4})", re.IGNORECASE)
CARD_FINAL_FROM_TEXT_RE = re.compile(r"Final\s+(\d{4})", re.IGNORECASE)

# Linha típica do Organize:
# 04/02/2026 Omercadeiroiii Mercado R$ -19,99
ORGANIZE_LINE_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+R\$\s*(-?[\d.,]+)\s*$"
)

def _detect_card_final(filename: str, full_text: str) -> Optional[str]:
    # 1) nome do arquivo "1748.pdf"
    stem = Path(filename).stem.strip()
    if stem.isdigit() and len(stem) == 4:
        return stem

    # 2) nome "final_1748.pdf"
    m = CARD_FINAL_FROM_FILENAME_RE.search(filename)
    if m:
        return m.group(1)

    # 3) fallback no texto
    m = CARD_FINAL_FROM_TEXT_RE.search(full_text or "")
    if m:
        return m.group(1)

    return None

def _create_transaction(
    card_final: str,
    date_str: str,
    desc_raw: str,
    amount_str: str,
    raw_lines: list[str],
) -> Optional[Transaction]:
    tx_date = parse_date(date_str)
    amount = parse_brl_value(amount_str)

    if tx_date is None or amount is None:
        return None

    # Organize vem invertido vs BTG -> normalizar invertendo
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

def parse_organize_pdf(pdf_path: str, pdf_password: Optional[str] = None) -> Iterator[Transaction]:
    logging.info(f"Iniciando análise do PDF do Organize: {pdf_path}")
    filename = Path(pdf_path).name

    with open_pdf(pdf_path, password=pdf_password) as pdf:
        full_text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        card_final = _detect_card_final(filename, full_text)

        if not card_final:
            logging.error(f"[Organize] Não foi possível determinar o final do cartão para '{filename}'. Pulando.")
            return

        all_transactions: list[Transaction] = []

        for page in pdf.pages:
            parsed_from_tables = 0

            # 1) tenta tabelas (mas NÃO pode impedir o fallback de texto)
            tables = page.extract_tables() or []
            for table in tables:
                # pode ser tabela de cabeçalho (saldo/total). Só processa linhas que pareçam transação.
                for row in table:
                    if not row or len(row) < 2:
                        continue

                    # data tem que ser dd/mm/yyyy
                    date_cell = (row[0] or "").strip()
                    if not re.match(r"^\d{2}/\d{2}/\d{2,4}$", date_cell):
                        continue

                    # tenta achar valor em alguma célula
                    amount_cell = None
                    for cell in reversed(row):
                        if cell is None:
                            continue
                        s = str(cell).strip()
                        if not s:
                            continue
                        # pode vir "-19,99" ou "R$ -19,99"
                        s2 = s.replace("R$", "").strip()
                        if re.match(r"^-?[\d.,]+$", s2):
                            amount_cell = s2
                            break

                    if not amount_cell:
                        continue

                    # descrição: junta colunas do meio (ignorando categoria/colunas vazias)
                    mid = []
                    for c in row[1:-1]:
                        if c is None:
                            continue
                        cs = str(c).strip()
                        if cs:
                            mid.append(cs)
                    desc_cell = " ".join(mid).strip() if mid else (str(row[1] or "").strip())

                    if not desc_cell:
                        continue

                    tx = _create_transaction(card_final, date_cell, desc_cell, amount_cell, [str(row)])
                    if tx:
                        all_transactions.append(tx)
                        parsed_from_tables += 1

            # 2) fallback por texto SEMPRE que não extrair nada útil das tabelas
            if parsed_from_tables == 0:
                page_text = page.extract_text() or ""
                for line in page_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    m = ORGANIZE_LINE_RE.match(line)
                    if not m:
                        continue

                    date_str, desc_raw, amount_str = m.groups()
                    tx = _create_transaction(card_final, date_str, desc_raw, amount_str, [line])
                    if tx:
                        all_transactions.append(tx)

        logging.info(f"[Organize] Arquivo={filename} card_final={card_final} transacoes_extraidas={len(all_transactions)}")
        yield from all_transactions
