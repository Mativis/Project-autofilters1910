"""
Flask app - versão de produção do sistema de confecção.
Stateless: nenhum dado é persistido. Processamento em memória por requisição.
"""
import io
import os
from datetime import date

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

from services.data_service import (
    load_excel, preparar_pedidos, preparar_estoque,
    processar_kanban, processar_dashboards, processar_estoque,
    processar_projecao, df_to_records, fmt_num, fmt_data,
)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/processar", methods=["POST"])
def processar():
    """Endpoint único: recebe os arquivos e retorna todos os dados processados."""
    try:
        pedidos_file = request.files.get("pedidos")
        estoque_file = request.files.get("estoque")
        projecao_file = request.files.get("projecao")

        df_pedidos_raw = load_excel(pedidos_file.read()) if pedidos_file else None
        df_estoque_raw = load_excel(estoque_file.read()) if estoque_file else None
        df_projecao_raw = load_excel(projecao_file.read()) if projecao_file else None

        params = request.form.to_dict()

        kanban = processar_kanban(df_pedidos_raw, df_estoque_raw)
        dashboards = processar_dashboards(df_pedidos_raw, df_estoque_raw)
        estoque = processar_estoque(df_estoque_raw, df_pedidos_raw)

        return jsonify({
            "success": True,
            "kanban": kanban,
            "dashboards": dashboards,
            "estoque": estoque,
            "has_projecao": df_projecao_raw is not None,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
