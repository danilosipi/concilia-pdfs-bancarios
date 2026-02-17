# concilia_pdfs/scripts/dump_card_1748.py
import os
import getpass
from pathlib import Path

from concilia_pdfs.parsers.btg_parser import parse_btg_pdf
from concilia_pdfs.parsers.organize_parser import parse_organize_pdf


def resolve_pwd() -> str | None:
    env_pwd = os.getenv("CONCILIA_PDF_PASSWORD")
    if env_pwd:
        return env_pwd
    try:
        pwd = getpass.getpass("Senha do PDF (ENTER para tentar sem senha): ").strip()
        return pwd if pwd else None
    except Exception:
        return None


BTG = Path("inputs/btg.pdf")
ORG = Path("inputs/organize_pdfs/1748.pdf")

pdf_password = resolve_pwd()

btg = [t for t in parse_btg_pdf(str(BTG), pdf_password=pdf_password) if t.card_final == "1748"]
org = list(parse_organize_pdf(str(ORG), pdf_password=pdf_password))

print("BTG 1748:", len(btg))
for t in sorted(btg, key=lambda x: float(x.amount)):
    print(t.tx_date, t.amount, t.description_raw)

print("\nORGANIZE 1748:", len(org))
for t in sorted(org, key=lambda x: float(x.amount)):
    print(t.tx_date, t.amount, t.description_raw)
