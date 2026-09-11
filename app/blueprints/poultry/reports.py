from flask import Response
from flask_login import login_required

from app.blueprints.poultry import poultry_bp
from app.blueprints.poultry.batches import _get_batch_or_403
from app.utils.pdf import render_batch_report_pdf
from app.utils.zootechnie import compute_fcr, feed_series, growth_curve_comparison, mortality_series


@poultry_bp.route("/lots/<int:batch_id>/rapport/pdf")
@login_required
def batch_report_pdf(batch_id):
    """Export PDF du rapport de lot (paragraphe 6)."""
    batch = _get_batch_or_403(batch_id)
    context = {
        "batch": batch,
        "fcr": compute_fcr(batch),
        "mortality_data": mortality_series(batch),
        "feed_data": feed_series(batch),
        "growth_data": growth_curve_comparison(batch),
    }
    pdf_bytes = render_batch_report_pdf(context)
    filename = f"rapport-lot-{batch.code}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )
