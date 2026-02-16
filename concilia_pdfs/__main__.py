import argparse
import logging
from pathlib import Path
import sys

# Add the project root to the Python path to allow absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from concilia_pdfs.parsers.btg_parser import parse_btg_pdf
from concilia_pdfs.parsers.organize_parser import parse_organize_pdf
from concilia_pdfs.core.reconciliation import reconcile_transactions
from concilia_pdfs.reporting.excel_writer import generate_excel_report

def main():
    """Função principal para executar a reconciliação de PDFs via CLI."""
    parser = argparse.ArgumentParser(
        description="Reconcilia extratos de cartão de crédito em PDF do BTG e do Organize."
    )
    parser.add_argument(
        "--btg",
        type=str,
        required=True,
        help="Caminho para o extrato em PDF do BTG."
    )
    parser.add_argument(
        "--organize_dir",
        type=str,
        required=True,
        help="Diretório contendo os extratos em PDF do Organize."
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Diretório de saída para os relatórios Excel."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Ativa o logging de depuração."
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("--- Iniciando Processo de Reconciliação de PDFs ---")

    # 1. Parse all BTG transactions
    btg_file = Path(args.btg)
    if not btg_file.is_file():
        logging.error(f"Arquivo BTG não encontrado: {btg_file}")
        return
    all_btg_txs = list(parse_btg_pdf(str(btg_file)))
    logging.info(f"Encontradas {len(all_btg_txs)} transações no total no PDF do BTG.")

    # 2. Parse all Organize transactions
    organize_dir = Path(args.organize_dir)
    if not organize_dir.is_dir():
        logging.error(f"Diretório do Organize não encontrado: {organize_dir}")
        return
    
    all_organize_txs = []
    org_files = list(organize_dir.glob("*.pdf"))
    for org_file in org_files:
        all_organize_txs.extend(list(parse_organize_pdf(str(org_file))))
    logging.info(f"Encontradas {len(all_organize_txs)} transações no total em {len(org_files)} PDFs do Organize.")

    # 3. Reconcile transactions
    reconciliation_results = reconcile_transactions(all_btg_txs, all_organize_txs)

    # 4. Generate reports
    generate_excel_report(reconciliation_results, all_btg_txs, all_organize_txs, args.out)

    logging.info("--- Processo de Reconciliação de PDFs Finalizado com Sucesso ---")

if __name__ == "__main__":
    main()
