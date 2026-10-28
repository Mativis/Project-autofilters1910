# Sistema de Confecção — Flask (Produção)

Versão web em Flask do sistema de confecção, com processamento **stateless**:
nenhum dado é persistido em disco ou banco. Os arquivos enviados são
processados em memória e descartados após a resposta.

## Funcionalidades

- **Kanban de Confecção**: planilha de pedidos por confecção, Q.E., prioridade.
- **Dashboards de Pedidos**: concentração de marca/código, volume, eficácia.
- **Análise de Estoque**: composição dos saldos, compra sugerida, tecido sugerido.
- **All for One**: visão consolidada (Pedidos + Estoque + Projeção).

## Como executar (desenvolvimento)

```bash
cd flask_app
pip install -r requirements.txt
python app.py
```

Acesse http://127.0.0.1:5000

## Produção (gunicorn)

```bash
cd flask_app
gunicorn -w 4 -b 0.0.0.0:5000 "app:app"
```

## Variáveis de ambiente

- `PORT`: porta (padrão 5000)
- `SECRET_KEY`: chave secreta (altere em produção)
- `FLASK_DEBUG`: `true` para debug (padrão false)

## Arquitetura

- `app.py` — entry point Flask, rotas e API
- `services/data_service.py` — processamento de dados (espelha `nucleo.py`)
- `templates/` — templates HTML
- `static/` — CSS e JS

Nenhum dado é salvo: os arquivos enviados são processados em memória e
descartados após a resposta HTTP.
