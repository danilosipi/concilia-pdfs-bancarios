# concilia_pdfs/parsers/btg_parser.py
from __future__ import annotations

import re
import logging
from datetime import date
from typing import Iterator, Optional, List, Dict, Any, Tuple

from concilia_pdfs.core.models import Transaction, Source
from concilia_pdfs.utils.normalization import normalize_text, parse_brl_value, parse_date_d_mon
from concilia_pdfs.utils.pdf_open import open_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

YEAR_RE = re.compile(r"de\s+(20\d{2})|Fatura\s+.*?(20\d{2})", re.IGNORECASE)

CARD_SECTION_RE = re.compile(
    r"Lançamentos\s+do\s+cart[aã]o.*?\bFinal\s+(\d{4})\b",
    re.IGNORECASE,
)

TX_DEBIT_RE = re.compile(
    r"^(\d{2}\s+\w{3})\s+(.+?)\s+R\$\s*([\d.,]+)\s*$",
    re.IGNORECASE,
)

TX_CREDIT_RE = re.compile(
    r"^(\d{2}\s+\w{3})\s+(.+?)\s*-\s*R\$\s*([\d.,]+)\s*$",
    re.IGNORECASE,
)

INTERNATIONAL_BASE_RE = re.compile(
    r"^(\d{2}\s+\w{3})\s+(.+?)\s+((?:[A-Z]{3})|(?:US\$)|(?:U\$))\s*([\d.,]+)\s*$",
    re.IGNORECASE,
)


CONVERSION_RE = re.compile(
    r"Convers[aã]o\s+para\s+Real\b.*?(?:R\$\s*)?(-?[\d.,]+)",
    re.IGNORECASE,
)

CONVERSION_WORD_RE = re.compile(r"Convers[aã]o\s+para\s+Real\b", re.IGNORECASE)
BRL_VALUE_IN_LINE_RE = re.compile(r"(?:R\$\s*)?(-?[\d]{1,3}(?:\.[\d]{3})*,[\d]{2}|-?[\d]+,[\d]{2})")


def _extract_year(text: str) -> int:
    m = YEAR_RE.search(text or "")
    if m:
        y = m.group(1) or m.group(2)
        if y:
            return int(y)
    return date.today().year


def _cluster_words_into_lines_split_columns(
    words: List[Dict[str, Any]],
    page_mid_x: float,
    y_tol: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Agrupa words por linha (top) e, dentro de cada linha, SEPARA por coluna (esq/dir) usando page_mid_x.
    Isso evita concatenar duas transações na mesma "linha".
    Retorna linhas com: top, x0, x1, text
    """
    if not words:
        return []

    words = sorted(words, key=lambda w: (float(w["top"]), float(w["x0"])))

    line_groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_top: Optional[float] = None

    for w in words:
        t = float(w["top"])
        if current_top is None:
            current_top = t
            current = [w]
            continue

        if abs(t - current_top) <= y_tol:
            current.append(w)
        else:
            line_groups.append(current)
            current_top = t
            current = [w]

    if current:
        line_groups.append(current)

    out: List[Dict[str, Any]] = []

    for group in line_groups:
        # divide por coluna
        left = [w for w in group if float(w["x0"]) < page_mid_x]
        right = [w for w in group if float(w["x0"]) >= page_mid_x]

        for part in (left, right):
            if not part:
                continue
            part = sorted(part, key=lambda w: float(w["x0"]))
            text = " ".join(w["text"] for w in part).strip()
            if not text:
                continue
            x0 = min(float(w["x0"]) for w in part)
            x1 = max(float(w["x1"]) for w in part)
            top = sum(float(w["top"]) for w in part) / len(part)
            out.append({"top": top, "x0": x0, "x1": x1, "text": text})

    # Ordena por top e x0 para leitura natural
    return sorted(out, key=lambda ln: (float(ln["top"]), float(ln["x0"])))


def _page_lines(page) -> List[Dict[str, Any]]:
    x0, y0, x1, y1 = page.bbox
    mid = (x0 + x1) / 2.0

    words = page.extract_words(
        keep_blank_chars=False,
        use_text_flow=False,   # importante: evita “colar” colunas
        x_tolerance=2,
        y_tolerance=2,
    ) or []

    return _cluster_words_into_lines_split_columns(words, page_mid_x=mid, y_tol=3.0)

def _extract_brl_from_line(line: str) -> Optional[float]:
    m = BRL_VALUE_IN_LINE_RE.search(line or "")
    if not m:
        return None
    return parse_brl_value(m.group(1))


def parse_btg_pdf(pdf_path: str, pdf_password: Optional[str] = None) -> Iterator[Transaction]:
    logging.info(f"Iniciando análise do PDF do BTG: {pdf_path}")

    with open_pdf(pdf_path, password=pdf_password) as pdf:
        full_text = "\n".join(page.extract_text(x_tolerance=2, y_tolerance=2) or "" for page in pdf.pages)
        pdf_year = _extract_year(full_text)

        current_card_final: Optional[str] = None

        for page in pdf.pages:
            lines = _page_lines(page)

            i = 0
            while i < len(lines):
                line = lines[i]["text"]

                # contexto do cartão
                msec = CARD_SECTION_RE.search(line)
                if msec:
                    current_card_final = msec.group(1)
                    i += 1
                    continue

                if not current_card_final:
                    i += 1
                    continue

                # internacional (pega BRL da conversão)
                mi = INTERNATIONAL_BASE_RE.match(line)
                if mi:
                    date_str, desc_raw, f_currency, f_amount_str = mi.groups()
                    raw_lines = [line]

                    brl_amount = None
                    pending_next_value = False

                    for j in range(1, 16):
                        if i + j >= len(lines):
                            break
                        nxt = lines[i + j]["text"]
                        raw_lines.append(nxt)

                        # caso 1: já veio “Conversão para Real ... 110,88”
                        mc = CONVERSION_RE.search(nxt)
                        if mc:
                            brl_amount = parse_brl_value(mc.group(1))
                            if brl_amount is not None:
                                break

                        # caso 2: veio só “Conversão para Real -” e o valor está na próxima linha
                        if CONVERSION_WORD_RE.search(nxt) and _extract_brl_from_line(nxt) is None:
                            pending_next_value = True
                            continue

                        if pending_next_value:
                            v = _extract_brl_from_line(nxt)
                            if v is not None:
                                brl_amount = v
                                break


                    if brl_amount is not None:
                        tx_date = parse_date_d_mon(date_str, pdf_year)
                        if tx_date:
                            yield Transaction(
                                card_final=current_card_final,
                                source=Source.BTG,
                                tx_date=tx_date,
                                description_raw=f"{desc_raw.strip()} (Internacional)",
                                description_norm=normalize_text(desc_raw),
                                amount=brl_amount,
                                foreign_currency=f_currency,
                                foreign_amount=parse_brl_value(f_amount_str),
                                raw_lines=raw_lines,
                            )
                    i += 1
                    continue

                # crédito (negativo)
                mc = TX_CREDIT_RE.match(line)
                if mc:
                    date_str, desc_raw, amount_str = mc.groups()
                    tx_date = parse_date_d_mon(date_str, pdf_year)
                    amt = parse_brl_value(amount_str)
                    if tx_date and amt is not None:
                        yield Transaction(
                            card_final=current_card_final,
                            source=Source.BTG,
                            tx_date=tx_date,
                            description_raw=desc_raw.strip(),
                            description_norm=normalize_text(desc_raw),
                            amount=amt * -1,
                            raw_lines=[line],
                        )
                    i += 1
                    continue

                # débito (positivo)
                md = TX_DEBIT_RE.match(line)
                if md:
                    date_str, desc_raw, amount_str = md.groups()
                    tx_date = parse_date_d_mon(date_str, pdf_year)
                    amt = parse_brl_value(amount_str)
                    if tx_date and amt is not None:
                        yield Transaction(
                            card_final=current_card_final,
                            source=Source.BTG,
                            tx_date=tx_date,
                            description_raw=desc_raw.strip(),
                            description_norm=normalize_text(desc_raw),
                            amount=amt,
                            raw_lines=[line],
                        )
                    i += 1
                    continue

                i += 1

    logging.info(f"Finalizada a análise do PDF do BTG: {pdf_path}")
