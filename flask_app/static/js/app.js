document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('btn-processar');
    const status = document.getElementById('status');

    btn.addEventListener('click', async () => {
        const pedidos = document.getElementById('pedidos').files[0];
        const estoque = document.getElementById('estoque').files[0];
        const projecao = document.getElementById('projecao').files[0];

        if (!pedidos && !projecao) {
            showStatus('Envie ao menos Pedidos ou Projeção.', 'error');
            return;
        }

        const formData = new FormData();
        if (pedidos) formData.append('pedidos', pedidos);
        if (estoque) formData.append('estoque', estoque);
        if (projecao) formData.append('projecao', projecao);

        btn.disabled = true;
        showStatus('Processando...', 'loading');

        try {
            const res = await fetch('/api/processar', { method: 'POST', body: formData });
            const data = await res.json();
            if (!data.success) {
                showStatus('Erro: ' + data.error, 'error');
                return;
            }
            renderResultados(data);
            showStatus('Processamento concluído com sucesso!', 'success');
        } catch (err) {
            showStatus('Erro de rede: ' + err.message, 'error');
        } finally {
            btn.disabled = false;
        }
    });

    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        });
    });
});

function showStatus(msg, type) {
    const status = document.getElementById('status');
    status.textContent = msg;
    status.className = 'status ' + type;
}

function renderResultados(data) {
    document.getElementById('resultados').style.display = 'block';
    document.getElementById('kpis').style.display = 'grid';

    // KPIs
    const kpis = document.getElementById('kpis');
    kpis.innerHTML = '';
    if (data.dashboards) {
        const k = data.dashboards.kpi;
        kpis.innerHTML = `
            <div class="kpi-card"><div class="label">Pedidos</div><div class="value">${k.pedidos}</div></div>
            <div class="kpi-card"><div class="label">Qtd Total</div><div class="value">${fmtNum(k.qtd_total)}</div></div>
            <div class="kpi-card"><div class="label">Saldo Total</div><div class="value">${fmtNum(k.saldo_total)}</div></div>
            <div class="kpi-card"><div class="label">Eficácia</div><div class="value">${(k.eficacia*100).toFixed(1)}%</div></div>
            <div class="kpi-card"><div class="label">Atrasados</div><div class="value">${k.atrasados}</div></div>
        `;
    }
    if (data.estoque) {
        const e = data.estoque;
        kpis.innerHTML += `
            <div class="kpi-card"><div class="label">Saldo 2 Total</div><div class="value">${fmtNum(e.saldo2_total)}</div></div>
            <div class="kpi-card"><div class="label">Saldo 5 Negativos</div><div class="value">${e.saldo5_negativos}</div></div>
            <div class="kpi-card"><div class="label">Compra Sugerida</div><div class="value">${fmtNum(e.total_compra)}</div></div>
            <div class="kpi-card"><div class="label">Tecido Sugerido (m)</div><div class="value">${e.total_tecido.toFixed(3)}</div></div>
        `;
    }

    // Kanban
    renderKanban(data.kanban);
    // Dashboards
    renderDashboards(data.dashboards);
    // Estoque
    renderEstoque(data.estoque);
}

function renderKanban(kanban) {
    const el = document.getElementById('kanban-content');
    if (!kanban || !kanban.length) { el.innerHTML = '<p>Nenhum dado de Kanban.</p>'; return; }
    let html = '';
    kanban.forEach(g => {
        html += `<div class="card"><h3>${g.confeccao}</h3>`;
        html += `<table class="data-table"><thead><tr><th>Compra</th><th>Cód</th><th>Confeccionado</th><th>Qtd</th><th>Saldo</th><th>Q.E.</th><th>Prioridade</th><th>Dt Entrega</th></tr></thead><tbody>`;
        g.itens.forEach(i => {
            html += `<tr><td>${i.compra}</td><td>${i.cod_confec}</td><td>${i.confeccionado}</td><td class="num">${fmtNum(i.qtd)}</td><td class="num">${fmtNum(i.saldo)}</td><td class="num">${fmtNum(i.qe)}</td><td>${i.prioridade}</td><td>${i.dt_entrega}</td></tr>`;
        });
        html += `</tbody></table><p><strong>Total Qtd:</strong> ${fmtNum(g.total_qtd)} | <strong>Total Saldo:</strong> ${fmtNum(g.total_saldo)}</p></div>`;
    });
    el.innerHTML = html;
}

function renderDashboards(d) {
    const el = document.getElementById('dashboards-content');
    if (!d) { el.innerHTML = '<p>Nenhum dado de dashboards.</p>'; return; }
    let html = '<div class="card"><h3>Top Marcas por Volume</h3>';
    html += '<table class="data-table"><thead><tr><th>Marca</th><th>Pedidos</th><th>Qtd</th><th>Saldo</th></tr></thead><tbody>';
    (d.top_marcas || []).forEach(m => {
        html += `<tr><td>${m.Marca}</td><td class="num">${m.Pedidos}</td><td class="num">${fmtNum(m.Qtd)}</td><td class="num">${fmtNum(m.Saldo)}</td></tr>`;
    });
    html += '</tbody></table></div>';

    html += '<div class="card"><h3>Top Códigos por Volume</h3>';
    html += '<table class="data-table"><thead><tr><th>Cód</th><th>Confeccionado</th><th>Qtd</th><th>Saldo</th></tr></thead><tbody>';
    (d.top_codigos || []).forEach(c => {
        html += `<tr><td>${c["Cód Confec"]}</td><td>${c.Confeccionado}</td><td class="num">${fmtNum(c.Qtd)}</td><td class="num">${fmtNum(c.Saldo)}</td></tr>`;
    });
    html += '</tbody></table></div>';

    html += '<div class="card"><h3>Status dos Pedidos</h3><table class="data-table"><thead><tr><th>Status</th><th>Quantidade</th></tr></thead><tbody>';
    for (const [k, v] of Object.entries(d.status_counts || {})) {
        html += `<tr><td>${k}</td><td class="num">${v}</td></tr>`;
    }
    html += '</tbody></table></div>';
    el.innerHTML = html;
}

function renderEstoque(e) {
    const el = document.getElementById('estoque-content');
    if (!e) { el.innerHTML = '<p>Nenhum dado de estoque.</p>'; return; }
    let html = '';
    if (e.compra_sugerida && e.compra_sugerida.length) {
        html += '<div class="card"><h3>🛒 Compra Sugerida</h3>';
        html += '<table class="data-table"><thead><tr><th>Cód</th><th>Descrição</th><th>Marca</th><th>Saldo 5</th><th>Compra Sugerida</th></tr></thead><tbody>';
        e.compra_sugerida.forEach(c => {
            html += `<tr><td>${c.cod_confec}</td><td>${c.descricao}</td><td>${c.marca}</td><td class="num">${fmtNum(c.saldo5)}</td><td class="num">${fmtNum(c.compra_sugerida)}</td></tr>`;
        });
        html += '</tbody></table></div>';
    }
    if (e.tecido_sugerido && e.tecido_sugerido.length) {
        html += '<div class="card"><h3>🧵 Tecido Sugerido</h3>';
        html += '<table class="data-table"><thead><tr><th>Cód</th><th>Descrição</th><th>Saldo 5</th><th>Tecido Sugerido (m)</th></tr></thead><tbody>';
        e.tecido_sugerido.forEach(t => {
            html += `<tr><td>${t.cod_confec}</td><td>${t.descricao}</td><td class="num">${fmtNum(t.saldo5)}</td><td class="num">${t.tecido_sugerido}</td></tr>`;
        });
        html += '</tbody></table></div>';
    }
    if (!html) html = '<p>Nenhum dado de estoque processado.</p>';
    el.innerHTML = html;
}

function fmtNum(v) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    const n = Number(v);
    if (Number.isInteger(n)) return n.toLocaleString('pt-BR');
    return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
