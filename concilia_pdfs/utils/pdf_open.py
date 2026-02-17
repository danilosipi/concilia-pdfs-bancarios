# concilia_pdfs/utils/pdf_open.py
import logging
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)

def open_pdf(path: str, password: Optional[str] = None):
    """
    Abre PDF com suporte a senha e logs melhores.

    Estratégia:
    - tenta abrir com password informado, depois "", depois None
    - se abrir, retorna o pdfplumber.PDF
    - se falhar, levanta a última exceção com log detalhado

    Observação:
    - Alguns PDFs criptografados não são suportados pelo backend do pdfplumber/pdfminer.
    """
    tried = []
    last_exc: Optional[BaseException] = None

    for pwd in (password, "", None):
        if pwd in tried:
            continue
        tried.append(pwd)
        try:
            pdf = pdfplumber.open(path, password=pwd)

            # Diagnóstico (quando disponível)
            try:
                encrypted = getattr(pdf, "pdf", None)
                if encrypted is not None and hasattr(encrypted, "is_encrypted"):
                    if encrypted.is_encrypted:
                        logger.info(f"PDF aberto e está criptografado (unlock OK). Arquivo: {path}")
            except Exception:
                pass

            return pdf

        except Exception as e:
            last_exc = e
            # log com tipo + repr para não ficar vazio
            logger.warning(
                f"Tentativa de abrir PDF falhou. arquivo={path} password={'<None>' if pwd is None else ('<vazia>' if pwd=='' else '<informada>')} "
                f"erro_tipo={type(e).__name__} erro={repr(e)}"
            )

    # Se chegou aqui, falhou tudo
    msg = (
        f"Não foi possível abrir PDF (possivelmente protegido ou criptografia não suportada): {path}. "
        f"Último erro: {type(last_exc).__name__ if last_exc else 'Unknown'} {repr(last_exc) if last_exc else ''}"
    )
    logger.error(msg)
    raise last_exc if last_exc else RuntimeError(msg)
