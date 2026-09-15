import csv
import io

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


@poultry_bp.route("/lots/<int:batch_id>/rapport/csv")
@login_required
def batch_report_csv(batch_id):
    """Export CSV jour par jour du lot (ouvrable dans Excel), pour un
    comptable ou une analyse personnelle - complement au PDF, plus adapte
    a la manipulation des chiffres."""
    batch = _get_batch_or_403(batch_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "Jour", "Date", "Aliment (kg)", "Eau (litres)", "Morts du jour",
        "Poids moyen (g)", "Cout aliment (FCFA)", "Cout medicaments (FCFA)", "Cout bois/litiere (FCFA)",
    ])

    for day in sorted(batch.days, key=lambda d: d.day_number):
        feed_cost = sum((r.quantity_kg or 0) * (r.unit_price or 0) for r in day.feed_records)
        medication_cost = sum((r.quantity or 0) * (r.unit_price or 0) for r in day.medication_records)
        wood_cost = sum((r.quantity or 0) * (r.unit_price or 0) for r in day.wood_records)
        last_weight = day.weight_records[-1].average_weight if day.weight_records else ""
        writer.writerow([
            day.day_number,
            day.date.strftime("%d/%m/%Y"),
            day.feed_kg,
            sum((r.quantity_liters or 0) for r in day.water_records),
            day.mortality_count,
            last_weight,
            feed_cost,
            medication_cost,
            wood_cost,
        ])

    filename = f"rapport-lot-{batch.code}.csv"
    return Response(
        "﻿" + buffer.getvalue(),  # BOM UTF-8 : Excel affiche correctement les accents
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
