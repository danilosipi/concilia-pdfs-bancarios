import re
import pdfplumber
from typing import Iterator
import logging
from datetime import date

from concilia_pdfs.core.models import Transaction, Source
from concilia_pdfs.utils.normalization import normalize_text, parse_brl_value, parse_date_d_mon

# Regex constants for BTG parser
CARD_FINAL_RE = re.compile(r"Final\s+(\d{4})")
TRANSACTION_RE = re.compile(r"(\d{2}\s+\w{3})\s+(.+?)\s+R\$\s+(-?[\d.,]+)")
INTERNATIONAL_BASE_RE = re.compile(r"(\d{2}\s+\w{3})\s+(.+?)\s+([A-Z]{3})\s+(-?[\d.,]+)")
CONVERSION_RE = re.compile(r"Conversão para Real - R\$\s+(-?[\d.,]+)")
YEAR_RE = re.compile(r"de\s+(20\d{2})|Fatura\s+.*(20\d{2})")

def _extract_year(text: str) -> int:
    """Extrai o ano do texto do PDF, usando o ano atual como fallback."""
    match = YEAR_RE.search(text)
    if match:
        # The regex has two capture groups, one will be None
        year_str = match.group(1) or match.group(2)
        if year_str:
            logging.info(f"Ano do documento detectado: {year_str}")
            return int(year_str)
    
    current_year = date.today().year
    logging.warning(f"Não foi possível detectar o ano no texto do PDF, usando o ano atual como fallback: {current_year}")
    return current_year

def parse_btg_pdf(pdf_path: str) -> Iterator[Transaction]:
    """
    Parses a BTG credit card statement PDF and yields normalized Transaction objects.
    """
    logging.info(f"Iniciando análise do PDF do BTG: {pdf_path}")
    current_card_final = None

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text(x_tolerance=2, y_tolerance=2) or "" for page in pdf.pages)
        
        pdf_year = _extract_year(full_text)
        lines = full_text.split('\n')
        lines_iter = iter(enumerate(lines))

        for i, line in lines_iter:
            # First, check for card final change
            card_match = CARD_FINAL_RE.search(line)
            if card_match:
                current_card_final = card_match.group(1)
                logging.info(f"Alternando para processar o cartão de final: {current_card_final}")
                continue

            if not current_card_final:
                continue

            # Check for international transactions (multi-line)
            international_match = INTERNATIONAL_BASE_RE.match(line)
            if international_match:
                raw_lines = [line]
                conversion_found = False
                # Look ahead for the conversion line
                for j in range(1, 6): # Look at the next 5 lines
                    next_line_index = i + j
                    if next_line_index < len(lines):
                        next_line = lines[next_line_index]
                        raw_lines.append(next_line)
                        conversion_match = CONVERSION_RE.search(next_line)
                        if conversion_match:
                            brl_amount_str = conversion_match.group(1)
                            brl_amount = parse_brl_value(brl_amount_str)
                            
                            date_str, desc_raw, f_currency, f_amount_str = international_match.groups()
                            tx_date = parse_date_d_mon(date_str, pdf_year)

                            if brl_amount is not None and tx_date:
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
                            
                            # Consume the lines we've processed from the iterator
                            for _ in range(j):
                                next(lines_iter, None)
                            
                            conversion_found = True
                            break # Exit look-ahead loop
                
                if not conversion_found:
                    logging.warning(f"Transação internacional encontrada, mas sem conversão para BRL próxima: '{line}'")
                continue # Move to the next transaction

            # Check for standard domestic transactions
            transaction_match = TRANSACTION_RE.match(line)
            if transaction_match:
                date_str, desc_raw, amount_str = transaction_match.groups()
                amount = parse_brl_value(amount_str)
                tx_date = parse_date_d_mon(date_str, pdf_year)

                if amount is not None and tx_date:
                    yield Transaction(
                        card_final=current_card_final,
                        source=Source.BTG,
                        tx_date=tx_date,
                        description_raw=desc_raw.strip(),
                        description_norm=normalize_text(desc_raw),
                        amount=amount,
                        raw_lines=[line],
                    )

    logging.info(f"Finalizada a análise do PDF do BTG: {pdf_path}")


if __name__ == '__main__':
    # To run this, you would need a sample BTG PDF in the correct path.
    # pdf_file = "path/to/your/btg_statement.pdf"
    # transactions = list(parse_btg_pdf(pdf_file))
    # for tx in transactions:
    #     print(tx.model_dump_json(indent=2))
    print("Módulo de análise do BTG carregado. Nenhum arquivo processado.")

