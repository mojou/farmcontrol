"""Export PDF du rapport de lot (paragraphe 6).

Utilise WeasyPrint pour transformer un template HTML/Jinja2 en PDF. Sur
Windows, WeasyPrint necessite les bibliotheques GTK3 (Pango/Cairo) - voir
README.md pour l'installation.
"""
from flask import render_template


def render_batch_report_pdf(context: dict) -> bytes:
    html_content = render_template("pdf/batch_report.html", **context)

    # Import differe : WeasyPrint charge des bibliotheques systeme (GTK) au
    # moment de l'import. On evite ainsi de faire planter tout le serveur au
    # demarrage si elles ne sont pas installees, et on renvoie une erreur
    # explicite uniquement lors d'un export PDF.
    from weasyprint import HTML

    return HTML(string=html_content).write_pdf()
