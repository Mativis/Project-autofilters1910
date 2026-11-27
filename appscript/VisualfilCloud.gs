/**
 * Visualfil Cloud — backend online do Visualfil em Google Sheets / Apps Script
 * ===========================================================================
 *
 * Este arquivo é independente do backend do Visual Kanban (Code.gs).
 * Publicar como App da Web (Implantar > Nova implantação > App da Web),
 * acesso: "Qualquer pessoa" e capturar a URL .../exec.
 *
 * Planilhas criadas automaticamente por inicializar():
 *   USUARIOS   - usuario, senha_sha, nome, admin, ativo
 *   PERMISSOES - usuario, pagina, nivel (visualizacao|total|restrito)
 *   DEMANDAS   - id, nome, fonte, criado_em, atualizado_em, arquivada, arquivo_id
 *   CATALOGO   - confeccao, codigo, item, tipo, tamanho, marca, atualizado_em
 *   ANALISES   - id, demanda_id, nome, criado_em, dados_json, usuario
 *   AGREGADOS  - id, demanda_id, dados_json, atualizado_em, stamp
 *
 * Seguranca: inicializar() so pode ser chamado pelo HTTP quando a aba USUARIOS
 * esta vazia E o segredo VF_SETUP_SECRET bate com p.setup_secret. O uso normal
 * e executar inicializar() manualmente no editor do Apps Script.
 *
 * Os XLSX ficam no Google Drive, em VisualfilCloud/<id da demanda>/<tipo>.xlsx
 */

var VF_VERSAO = '1.4.0';
var VF_PASTA = 'VisualfilCloud';

function doPost(e) {
  try {
    var evt = e || {};
    var post = evt.postData || {};
    var bruto = post.contents || '{}';
    var p;
    try { p = JSON.parse(bruto) || {}; }
    catch (erroPayload) { throw new Error('Payload inválido: ' + String(bruto).slice(0, 80)); }
    var acao = String(p.action || '').toLowerCase();
    // cred_usuario/cred_senha permitem enviar `usuario` como alvo (admin)
    var usuario = String(p.cred_usuario || p.usuario || p.user || '').trim();
    var senha = String(p.cred_senha || p.senha || '').trim();

    if (acao === 'ping') return _ok({ versao: VF_VERSAO, hora: new Date().toISOString() });
    if (acao === 'inicializar') {
      var segredo = PropertiesService.getScriptProperties().getProperty('VF_SETUP_SECRET') || '';
      if (!segredo || String(p.setup_secret || '') !== segredo) {
        throw new Error('Inicializacao bloqueada. Defina VF_SETUP_SECRET ou execute inicializar() no editor.');
      }
      if (_aba('USUARIOS').getData().length) {
        throw new Error('Ja existem usuarios; inicializacao nao permitida.');
      }
      return _acaoInicializar(p);
    }
    if (acao === 'login') return _acaoLogin(usuario, senha);

    // Demais ações exigem login
    var user = _autenticar(usuario, senha);
    if (!user) throw new Error('Usuário ou senha inválidos.');

    switch (acao) {
      case 'demandas_listar': return _exigir(user, 'visualizacao'), _ok({ demandas: _aba('DEMANDAS').getData() });
      case 'demanda_salvar': return _admin(user), _acaoDemandaSalvar(p);
      case 'demanda_excluir': return _admin(user), _acaoDemandaExcluir(p);
      case 'demanda_arquivar': return _admin(user), _acaoDemandaArquivar(p);
      case 'demanda_desarquivar': return _admin(user), _acaoDemandaDesarquivar(p);
      case 'arquivo_salvar': return _admin(user), _acaoArquivoSalvar(p);
      case 'arquivo_ler': return _exigir(user, 'visualizacao'), _acaoArquivoLer(p);
      case 'arquivos_ler': return _exigir(user, 'visualizacao'), _acaoArquivosLer(p);
      case 'agregado_salvar': return _exigir(user, 'total'), _acaoAgregadoSalvar(p);
      case 'agregado_ler': return _exigir(user, 'visualizacao'), _acaoAgregadoLer(p);
      case 'arquivos_listar': return _exigir(user, 'visualizacao'), _ok({ arquivos: _listarArquivos(p.demanda_id) });
      case 'usuarios_listar': return _admin(user), _ok({ usuarios: _aba('USUARIOS').getData() });
      case 'usuario_salvar': return _admin(user), _acaoUsuarioSalvar(p, user);
      case 'permissoes_listar': return _admin(user), _ok({ permissoes: _aba('PERMISSOES').getData() });
      case 'permissoes_minhas': return _exigir(user, 'visualizacao'), _ok({ permissoes: _aba('PERMISSOES').getData().filter(function (r) {
        return String(r.usuario || '').toLowerCase() === String((user || {}).usuario || '').toLowerCase();
      }) });
      case 'permissao_salvar': return _admin(user), _acaoPermissaoSalvar(p);
      case 'catalogo_listar': return _exigir(user, 'visualizacao'), _ok({ catalogo: _aba('CATALOGO').getData() });
      case 'catalogo_salvar': return _admin(user), _acaoCatalogoSalvar(p);
      case 'catalogo_excluir': return _admin(user), _acaoCatalogoExcluir(p);
      case 'analise_salvar': return _exigir(user, 'total'), _acaoAnaliseSalvar(p, user);
      case 'analises_listar': return _exigir(user, 'visualizacao'), _ok({ analises: _aba('ANALISES').getData() });
      case 'analise_excluir': return _admin(user), _acaoAnaliseExcluir(p, user);
      case 'tokens_web_listar': return _admin(user), _acaoTokensWebListar();
      case 'token_web_salvar': return _admin(user), _acaoTokenWebSalvar(p);
      case 'token_web_excluir': return _admin(user), _acaoTokenWebExcluir(p);
      default: throw new Error('Ação desconhecida: ' + acao);
    }
  } catch (erro) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, erro: String(erro && erro.message || erro) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function _normConf(v) {
  return String(v || '').trim().toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ');
}

function _lerTokensConf() {
  var bruto = String(PropertiesService.getScriptProperties().getProperty('VF_CONF_TOKENS_JSON') || '').trim();
  if (!bruto) return {};
  try {
    var obj = JSON.parse(bruto);
    return obj && typeof obj === 'object' ? obj : {};
  } catch (e) { return {}; }
}

function _salvarTokensConf(obj) {
  PropertiesService.getScriptProperties().setProperty('VF_CONF_TOKENS_JSON', JSON.stringify(obj || {}));
}

function _confsDoToken(ent) {
  if (typeof ent === 'string') return [ent].filter(Boolean);
  var arr = Array.isArray(ent.confeccoes) ? ent.confeccoes : (ent.confeccao ? [ent.confeccao] : []);
  return arr.map(function (c) { return String(c || '').trim(); }).filter(Boolean);
}

function _resolverLeitura(p) {
  var recebido = String((p && (p.token || p.read_token || p.t)) || '').trim();
  var adminToken = String(PropertiesService.getScriptProperties().getProperty('VF_READ_TOKEN') || '').trim();
  var confTokens = _lerTokensConf();
  var temConfTokens = Object.keys(confTokens).length > 0;

  if (adminToken && recebido && recebido === adminToken) {
    return { ok: true, tipo: 'admin', confeccoes: [] };
  }
  if (recebido && confTokens[recebido]) {
    var entrada = confTokens[recebido];
    var confs = _confsDoToken(entrada);
    var ativo = typeof entrada === 'object' ? String((entrada || {}).ativo) !== 'false' : true;
    if (ativo && confs.length) return { ok: true, tipo: 'conf', confeccoes: confs };
  }
  if (!adminToken && !temConfTokens) return { ok: true, tipo: 'aberto', confeccoes: [] };
  if (!recebido) return { ok: false, erro: 'Token de leitura obrigatório.' };
  return { ok: false, erro: 'Token de leitura inválido.' };
}

function _gerarTokenWeb() {
  return 'vf_' + Utilities.getUuid().replace(/-/g, '').slice(0, 24);
}

function _acaoTokensWebListar() {
  var mapa = _lerTokensConf();
  var tokens = Object.keys(mapa).map(function (token) {
    var ent = mapa[token];
    var confs = _confsDoToken(ent);
    var ativo = typeof ent === 'object' ? String((ent || {}).ativo) !== 'false' : true;
    return { token: token, confeccoes: confs, confeccao: confs.join(', '), ativo: ativo };
  }).sort(function (a, b) { return String(a.confeccao).localeCompare(String(b.confeccao)); });
  return _ok({ tokens: tokens });
}

function _acaoTokenWebSalvar(p) {
  var confs = Array.isArray(p.confeccoes) ? p.confeccoes : String(p.confeccao || p.confeccoes || '').split(',');
  confs = confs.map(function (c) { return String(c || '').trim(); }).filter(Boolean);
  // dedupe case-insensitive
  var seen = {};
  confs = confs.filter(function (c) { var k = _normConf(c); if (seen[k]) return false; seen[k]=true; return true; });
  if (!confs.length) throw new Error('Informe ao menos uma confecção.');
  var mapa = _lerTokensConf();
  var token = String(p.token || '').trim();
  if (!token) token = _gerarTokenWeb();
  var ativo = p.ativo === false ? false : true;
  mapa[token] = { confeccoes: confs, ativo: ativo, atualizado_em: new Date().toISOString() };
  _salvarTokensConf(mapa);
  return _ok({ token: token, confeccoes: confs, ativo: ativo });
}

function _acaoTokenWebExcluir(p) {
  var token = String(p.token || '').trim();
  var mapa = _lerTokensConf();
  if (token && mapa[token]) delete mapa[token];
  _salvarTokensConf(mapa);
  return _ok({});
}

function _filtrarPorConfeccoes(dados, confeccoes) {
  var alvos = (confeccoes || []).map(_normConf).filter(Boolean);
  if (!alvos.length || !dados || typeof dados !== 'object') return dados;
  var set = {};
  alvos.forEach(function(a){ set[a]=true; });
  var out = JSON.parse(JSON.stringify(dados));

  function matchConf(obj) {
    var c = obj.confeccao || obj['Confecção'] || obj['Confecao'] || obj.conf || obj.grupo || obj.Grupo || obj['CONFECCAO'] || '';
    return !!set[_normConf(c)];
  }

  if (Array.isArray(out.cards)) out.cards = out.cards.filter(matchConf);
  if (Array.isArray(out.pedidos)) out.pedidos = out.pedidos.filter(matchConf);
  if (Array.isArray(out.compra_itens)) out.compra_itens = out.compra_itens.filter(matchConf);
  if (Array.isArray(out.compra_resumo)) out.compra_resumo = out.compra_resumo.filter(matchConf);
  if (Array.isArray(out.capacidade)) out.capacidade = out.capacidade.filter(matchConf);
  if (Array.isArray(out.por_confeccao)) out.por_confeccao = out.por_confeccao.filter(function (r) { return !!set[_normConf(r.Grupo || r.grupo || r.confeccao)]; });
  if (Array.isArray(out.resumo_confeccao)) out.resumo_confeccao = out.resumo_confeccao.filter(function (r) { return !!set[_normConf(r.confeccao || r.Confeccao || r['Confecção'])]; });

  // Recalcula KPIs/resumos dos cards filtrados
  var cards = out.cards || [];
  var totalQe = 0, atrasados = 0, saldo = 0, codigos = {};
  var porPri = {}, porClass = {};
  cards.forEach(function (c) {
    var qe = Number(c.qe || 0) || 0;
    var sal = Number(c.saldo || 0) || 0;
    var pri = String(c.prioridade || 'Média');
    var cls = String(c.classificacao || 'Sem classificação');
    totalQe += qe; saldo += sal;
    if (pri === 'Atrasado') atrasados += 1;
    if (c.codigo) codigos[String(c.codigo)] = true;
    porPri[pri] = (porPri[pri] || 0) + 1;
    porClass[cls] = porClass[cls] || { classificacao: cls, pedidos: 0, saldo: 0, qe: 0 };
    porClass[cls].pedidos += 1; porClass[cls].saldo += sal; porClass[cls].qe += qe;
  });
  out.total_qe = totalQe;
  out.codigos_negativos = Object.keys(codigos).length;
  out.kpis = {
    'Pedidos': cards.length,
    'Atrasados': atrasados,
    'Saldo': Math.round(saldo),
    'Q.E.': Math.round(totalQe)
  };
  out.resumo_classificacao = Object.keys(porClass).map(function (k) { return porClass[k]; });
  out.por_status = Object.keys(porPri).map(function (k) { return { Grupo: k, Pedidos: porPri[k] }; });
  out.por_prioridade = out.por_status.slice();
  out.confeccoes_filtradas = confeccoes;
  out.confeccao_filtrada = confeccoes.join(', ');
  return out;
}

function _saidaJson(obj, callback) {
  if (callback) {
    var cb = String(callback).replace(/[^\w$.]/g, '');
    return ContentService.createTextOutput(cb + '(' + JSON.stringify(obj) + ');')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  try {
    var p = (e && e.parameter) ? e.parameter : {};
    var acao = String(p.action || '').toLowerCase();
    var callback = String(p.callback || '').trim();

    if (!acao || acao === 'ping') {
      return _saidaJson({ ok: true, versao: VF_VERSAO, nome: 'Visualfil Cloud API' }, callback);
    }

    var auth = _resolverLeitura(p);
    if (!auth.ok) return _saidaJson({ ok: false, erro: auth.erro }, callback);

    if (acao === 'demandas' || acao === 'demandas_listar') {
      var demandas = _aba('DEMANDAS').getData().filter(function (d) { return String(d.arquivada || 'NAO') !== 'SIM'; });
      return _saidaJson({ ok: true, versao: VF_VERSAO, demandas: demandas, perfil: auth.tipo, confeccoes: auth.confeccoes || [] }, callback);
    }

    if (acao === 'kanban' || acao === 'agregado') {
      var demanda = String(p.demanda_id || p.demanda || '').trim();
      if (!demanda) return _saidaJson({ ok: false, erro: 'Informe demanda_id.' }, callback);
      var res = _acaoAgregadoLer({ demanda_id: demanda });
      var payload = JSON.parse(res.getContent());
      if (payload.ok && auth.tipo === 'conf' && (auth.confeccoes || []).length) {
        payload.dados = _filtrarPorConfeccoes(payload.dados || {}, auth.confeccoes);
        payload.confeccoes_filtradas = auth.confeccoes;
        payload.confeccao_filtrada = auth.confeccoes.join(', ');
      }
      payload.versao = VF_VERSAO;
      payload.demanda_id = demanda;
      payload.perfil = auth.tipo;
      return _saidaJson(payload, callback);
    }

    return _saidaJson({ ok: false, erro: 'Ação GET desconhecida: ' + acao }, callback);
  } catch (erro) {
    var cb = String(((e && e.parameter) || {}).callback || '').trim();
    return _saidaJson({ ok: false, erro: String(erro && erro.message || erro) }, cb);
  }
}

/** Executar uma vez no editor do Apps Script para criar planilhas e o admin. */
function inicializar() {
  var r = _acaoInicializar({ usuario: 'admin', senha: 'admin' });
  Logger.log(r.getContent());
  return r;
}

/* ============================== utilitários ============================== */

function _ok(obj) {
  var r = Object.assign({ ok: true }, obj || {});
  return ContentService.createTextOutput(JSON.stringify(r)).setMimeType(ContentService.MimeType.JSON);
}

function _sha(texto) {
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(texto), Utilities.Charset.UTF_8);
  return bytes.map(function (b) { return ('0' + ((b & 0xff).toString(16))).slice(-2); }).join('');
}

function _planilha() {
  // Funciona tanto em projeto vinculado a uma planilha quanto em projeto avulso:
  // nesse último, defina VF_SPREADSHEET_ID nas Propriedades do Script.
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('VF_SPREADSHEET_ID');
  var ss = id ? SpreadsheetApp.openById(id) : SpreadsheetApp.getActiveSpreadsheet();
  if (!ss) {
    throw new Error('Planilha não encontrada. Vincule o projeto a uma planilha ou defina VF_SPREADSHEET_ID nas propriedades do script.');
  }
  return ss;
}

function _aba(nome) {
  var ss = _planilha();
  var sh = ss.getSheetByName(nome);
  if (!sh) sh = ss.insertSheet(nome);
  return {
    sheet: sh,
    cabecalhos: function () {
      var vals = sh.getRange(1, 1, 1, Math.max(1, sh.getLastColumn())).getValues()[0];
      return vals.map(function (v) { return String(v || '').trim(); });
    },
    // linhas reais da planilha (sem filtrar vazias) — usado para salvar/excluir
    reais: function () {
      if (sh.getLastRow() < 2) return [];
      var cols = Math.max(1, sh.getLastColumn());
      var vals = sh.getRange(2, 1, sh.getLastRow() - 1, cols).getValues();
      var head = this.cabecalhos();
      return vals.map(function (row) {
        var o = {};
        head.forEach(function (h, i) { if (h) o[h] = row[i]; });
        return o;
      });
    },
    getData: function () {
      return this.reais().filter(function (o) {
        return Object.keys(o).some(function (k) { return String(o[k] || '').trim() !== ''; });
      });
    },
    salvar: function (registro, chave, valor) {
      var head = this.cabecalhos();
      var linhas = this.reais();
      var idx = -1;
      for (var i = 0; i < linhas.length; i++) {
        if (String(linhas[i][chave] || '') === String(valor || '')) { idx = i; break; }
      }
      var nova = head.map(function (h) { return registro[h] === undefined ? '' : registro[h]; });
      if (idx >= 0) sh.getRange(idx + 2, 1, 1, head.length).setValues([nova]);
      else sh.appendRow(nova);
    },
    excluir: function (chave, valor) {
      var linhas = this.reais();
      for (var i = linhas.length - 1; i >= 0; i--) {
        if (String(linhas[i][chave] || '') === String(valor || '')) sh.deleteRow(i + 2);
      }
    }
  };
}

function _garantirCabecalhos(nome, head) {
  var ss = _planilha();
  var sh = ss.getSheetByName(nome) || ss.insertSheet(nome);
  if (sh.getLastRow() < 1) {
    sh.getRange(1, 1, 1, head.length).setValues([head]);
    return;
  }
  // migração: acrescenta colunas novas sem apagar dados existentes
  var atual = sh.getRange(1, 1, 1, Math.max(1, sh.getLastColumn())).getValues()[0]
    .map(function (v) { return String(v || '').trim(); });
  head.forEach(function (h, i) {
    if (atual.indexOf(h) < 0) sh.getRange(1, i + 1).setValue(h);
  });
}

function _ehAdmin(user) {
  return String((user || {}).admin || '').toUpperCase() === 'SIM' || (user || {}).admin === true;
}

function _admin(user) {
  if (!_ehAdmin(user) && String((user || {}).admin || '') !== 'true') {
    throw new Error('Permissão negada: somente administrador.');
  }
}

var NIVEIS_ORDEM = { restrito: 0, visualizacao: 1, total: 2 };

/**
 * Aplica as permissões da aba PERMISSOES. Compatibilidade: se a aba estiver
 * vazia (instalação antiga), mantém o acesso como antes. Se houver regras,
 * o usuário precisa ter pelo menos uma página com o nível pedido.
 */
function _exigir(user, nivelMinimo) {
  if (_ehAdmin(user) || String((user || {}).admin || '') === 'true') return;
  var regras = _aba('PERMISSOES').getData();
  if (!regras.length) return;
  var eu = String((user || {}).usuario || '').toLowerCase();
  var minhas = regras.filter(function (r) {
    return String(r.usuario || '').toLowerCase() === eu;
  });
  if (!minhas.length) throw new Error('Permissão negada para este usuário.');
  var melhor = -1;
  minhas.forEach(function (r) {
    var n = NIVEIS_ORDEM[String(r.nivel || '').toLowerCase()];
    if (n !== undefined && n > melhor) melhor = n;
  });
  var necessario = NIVEIS_ORDEM[String(nivelMinimo || 'visualizacao')] === undefined
    ? 1 : NIVEIS_ORDEM[String(nivelMinimo || 'visualizacao')];
  if (melhor < necessario) {
    throw new Error('Permissão negada: é necessário nível ' + nivelMinimo + '.');
  }
}

function _autenticar(usuario, senha) {
  if (!usuario || !senha) return null;
  var hash = _sha(usuario.toLowerCase() + ':' + senha);
  var users = _aba('USUARIOS').getData();
  for (var i = 0; i < users.length; i++) {
    var u = users[i] || {};
    if (String(u.usuario || '').toLowerCase() === usuario.toLowerCase() &&
        String(u.senha_sha || '') === hash &&
        String(u.ativo || 'SIM').toUpperCase() !== 'NAO') {
      return u;
    }
  }
  return null;
}

/* ============================== ações ============================== */

function _acaoInicializar(p) {
  _garantirCabecalhos('USUARIOS', ['usuario', 'senha_sha', 'nome', 'admin', 'ativo']);
  _garantirCabecalhos('PERMISSOES', ['id', 'usuario', 'pagina', 'nivel']);
  _garantirCabecalhos('DEMANDAS', ['id', 'nome', 'fonte', 'criado_em', 'atualizado_em', 'arquivada', 'arquivo_id']);
  _garantirCabecalhos('CATALOGO', ['confeccao', 'codigo', 'item', 'tipo', 'tamanho', 'marca', 'atualizado_em']);
  _garantirCabecalhos('ANALISES', ['id', 'demanda_id', 'nome', 'criado_em', 'dados_json', 'usuario']);
  _garantirCabecalhos('AGREGADOS', ['id', 'demanda_id', 'dados_json', 'atualizado_em', 'stamp']);

  var adminUser = String(p.usuario || 'admin').trim();
  var adminSenha = String(p.senha || 'admin').trim();
  var users = _aba('USUARIOS').getData();
  var existe = users.some(function (u) { return u && String(u.usuario || '') === adminUser; });
  if (!existe) {
    _aba('USUARIOS').salvar({
      usuario: adminUser,
      senha_sha: _sha(adminUser.toLowerCase() + ':' + adminSenha),
      nome: 'Administrador',
      admin: 'SIM',
      ativo: 'SIM'
    }, 'usuario', adminUser);
  }
  return _ok({ versao: VF_VERSAO, admin: adminUser, aviso: 'Troque a senha do admin após o primeiro login.' });
}

function _acaoLogin(usuario, senha) {
  var u = _autenticar(usuario, senha);
  if (!u) throw new Error('Usuário ou senha inválidos.');
  return _ok({
    usuario: u.usuario,
    nome: u.nome || u.usuario,
    admin: String(u.admin || '').toUpperCase() === 'SIM' || u.admin === 'true'
  });
}

function _novoId(prefixo) {
  return prefixo + '-' + Utilities.getUuid().slice(0, 8);
}

function _acaoDemandaSalvar(p) {
  var id = String(p.id || '').trim() || _novoId('DEM');
  var ago = new Date().toISOString();
  var atual = _aba('DEMANDAS').getData().filter(function (d) { return String(d.id || '') === id; })[0] || {};
  var registro = Object.assign({}, atual, {
    id: id,
    nome: String(p.nome || '').trim(),
    fonte: String(p.fonte || p.remessa || '').trim(),
    criado_em: atual.criado_em || ago,
    atualizado_em: ago
  });
  _aba('DEMANDAS').salvar(registro, 'id', id);
  return _ok({ id: id });
}

function _agremover(id) {
  _aba('AGREGADOS').excluir('demanda_id', String(id || ''));
}

function _removerAbasDemanda(id) {
  var ss = _planilha();
  TIPOS_OK.forEach(function (tipo) {
    var nome = _nomeAba(id, tipo);
    var sh = ss.getSheetByName(nome);
    if (sh) ss.deleteSheet(sh);
  });
}

function _stampDemanda(id) {
  var d = _aba('DEMANDAS').getData().filter(function (x) { return String(x.id || '') === String(id || ''); })[0] || {};
  return String(d.atualizado_em || '');
}

function _acaoDemandaExcluir(p) {
  var id = String(p.id || '').trim();
  if (!id) throw new Error('Informe o id da demanda.');
  var d = _aba('DEMANDAS').getData().filter(function (x) { return String(x.id || '') === id; })[0] || {};
  _removerAbasDemanda(id);
  _agremover(id);
  _aba('DEMANDAS').excluir('id', id);
  var pasta = _pastaDemanda(id, false);
  if (pasta) {
    var files = pasta.getFiles();
    while (files.hasNext()) files.next().setTrashed(true);
  }
  if (d.arquivo_id) {
    try { DriveApp.getFileById(String(d.arquivo_id)).setTrashed(true); } catch (e) { /* ja removido */ }
  }
  return _ok({});
}

function _pastaRaiz(criar) {
  var pastas = DriveApp.getFoldersByName(VF_PASTA);
  if (pastas.hasNext()) return pastas.next();
  return criar ? DriveApp.createFolder(VF_PASTA) : null;
}

function _pastaDemanda(id, criar) {
  var raiz = _pastaRaiz(criar);
  if (!raiz) return null;
  var pastas = raiz.getFoldersByName(String(id));
  if (pastas.hasNext()) return pastas.next();
  return criar ? raiz.createFolder(String(id)) : null;
}

/* ================= planilhas vinculadas (rápido) ================= */

var PASTA_ARQUIVO = 'VisualfilArquivado';

function _nomeAba(demandaId, tipo) {
  var raw = 'D_' + String(demandaId || '').replace(/[^A-Za-z0-9_-]/g, '_') + '_' + String(tipo || '');
  return raw.slice(0, 100);
}

function _abaOuCriar(nome) {
  var sh = _planilha().getSheetByName(nome);
  if (!sh) sh = _planilha().insertSheet(nome);
  return sh;
}

function _demandaArquivada(id) {
  var d = _aba('DEMANDAS').getData().filter(function (x) { return String(x.id || '') === String(id || ''); })[0] || {};
  return String(d.arquivada || '').toUpperCase() === 'SIM';
}

function _escreverAba(demandaId, tipo, colunas, linhas) {
  var sh = _abaOuCriar(_nomeAba(demandaId, tipo));
  sh.clear();
  var head = colunas || [];
  var corpo = linhas || [];
  var nCol = corpo.reduce(function (max, linha) {
    return Math.max(max, (linha || []).length);
  }, Math.max(1, head.length));
  var valores = [head];
  corpo.forEach(function (linha) {
    var l = [];
    for (var c = 0; c < nCol; c++) l.push(linha[c] === undefined ? '' : linha[c]);
    valores.push(l);
  });
  sh.getRange(1, 1, valores.length, nCol).setValues(valores);
  return { linhas: corpo.length, colunas: nCol };
}

function _lerAba(demandaId, tipo) {
  var nome = _nomeAba(demandaId, tipo);
  var sh = _planilha().getSheetByName(nome);
  if (!sh || sh.getLastRow() < 1) return null;
  var vals = sh.getDataRange().getValues();
  if (!vals.length) return null;
  var colunas = vals[0].map(function (v) { return String(v || ''); });
  if (!colunas.some(function (c) { return String(c).trim() !== ''; })) return null;
  var linhas = vals.slice(1).filter(function (r) {
    return r.some(function (v) { return String(v || '').trim() !== ''; });
  });
  return { colunas: colunas, linhas: linhas };
}

function _pastaArquivo(criar) {
  var pastas = DriveApp.getFoldersByName(PASTA_ARQUIVO);
  if (pastas.hasNext()) return pastas.next();
  return criar ? DriveApp.createFolder(PASTA_ARQUIVO) : null;
}

function _tabArquivo(id) {
  var nome = 'VisualfilArquivo_' + String(id || '').replace(/[^A-Za-z0-9_-]/g, '_');
  var arquivos = DriveApp.getFilesByName(nome);
  if (arquivos.hasNext()) return SpreadsheetApp.open(arquivos.next());
  return SpreadsheetApp.create(nome);
}

function _acaoDemandaArquivar(p) {
  var id = String(p.demanda_id || p.id || '').trim();
  if (!id) throw new Error('Informe a demanda.');
  if (_demandaArquivada(id)) return _ok({ id: id, arquivada: true });

  var destino = _tabArquivo(id);
  var tipos = TIPOS_OK.slice();
  var copiadas = [];
  // fase 1: copia e valida TUDO antes de mexer na planilha principal
  tipos.forEach(function (tipo) {
    var dados = _lerAba(id, tipo);
    if (!dados) return;
    var nome = _nomeAba(id, tipo);
    var sh = destino.getSheetByName(nome) || destino.insertSheet(nome);
    sh.clear();
    var valores = [dados.colunas].concat(dados.linhas);
    sh.getRange(1, 1, valores.length, Math.max(1, dados.colunas.length)).setValues(valores);
    if (sh.getLastRow() < valores.length) {
      throw new Error('Falha ao copiar ' + tipo + ' para o arquivamento.');
    }
    copiadas.push(tipo);
  });

  var file = DriveApp.getFileById(destino.getId());
  var pasta = _pastaArquivo(true);
  pasta.addFile(file);
  try { DriveApp.getRootFolder().removeFile(file); } catch (e) { /* ja estava só na pasta */ }

  // fase 2: metadados primeiro (evita orphan)
  var d = _aba('DEMANDAS').getData().filter(function (x) { return String(x.id || '') === id; })[0] || {};
  d.arquivada = 'SIM';
  d.arquivo_id = destino.getId();
  d.atualizado_em = new Date().toISOString();
  _aba('DEMANDAS').salvar(d, 'id', id);
  _agremover(id);

  // fase 3: remove as abas da planilha principal
  tipos.forEach(function (tipo) {
    if (copiadas.indexOf(tipo) < 0) return;
    var original = _planilha().getSheetByName(_nomeAba(id, tipo));
    if (original) _planilha().deleteSheet(original);
  });
  return _ok({ id: id, arquivada: true, arquivo_id: destino.getId() });
}

function _acaoDemandaDesarquivar(p) {
  var id = String(p.demanda_id || p.id || '').trim();
  if (!id) throw new Error('Informe a demanda.');
  var d = _aba('DEMANDAS').getData().filter(function (x) { return String(x.id || '') === id; })[0] || {};
  var arquivoId = String(d.arquivo_id || '');
  if (!arquivoId) throw new Error('Demanda sem planilha arquivada vinculada.');

  // restaura tudo; qualquer falha aborta SEM alterar o estado da demanda
  var destino = SpreadsheetApp.openById(arquivoId);
  var restauradas = [];
  TIPOS_OK.forEach(function (tipo) {
    var dados = _lerArquivoAba(destino, _nomeAba(id, tipo));
    if (!dados) return;
    _escreverAba(id, tipo, dados.colunas, dados.linhas);
    restauradas.push(tipo);
  });
  restauradas.forEach(function (tipo) {
    var conferida = _lerAba(id, tipo);
    if (!conferida) throw new Error('Falha ao restaurar ' + tipo + '.');
  });

  d.arquivada = 'NAO';
  d.atualizado_em = new Date().toISOString();
  // mantém arquivo_id como backup; NÃO descarta a planilha arquivada
  _aba('DEMANDAS').salvar(d, 'id', id);
  _agremover(id);
  return _ok({ id: id, arquivada: false, arquivo_id: arquivoId });
}

function _lerArquivoAba(spreadsheet, nome) {
  var sh = spreadsheet.getSheetByName(nome);
  if (!sh || sh.getLastRow() < 1) return null;
  var vals = sh.getDataRange().getValues();
  var colunas = vals[0].map(function (v) { return String(v || ''); });
  var linhas = vals.slice(1).filter(function (r) {
    return r.some(function (v) { return String(v || '').trim() !== ''; });
  });
  return { colunas: colunas, linhas: linhas };
}

var TIPOS_OK = ['pedidos', 'estoque', 'producao', 'projecao'];

function _idSeguro(id) {
  return String(id || '').trim().replace(/[^A-Za-z0-9_-]/g, '_');
}

function _acaoArquivoSalvar(p) {
  var id = _idSeguro(p.demanda_id);
  var tipo = String(p.tipo || '').trim().toLowerCase();
  if (!id) throw new Error('Informe a demanda.');
  if (TIPOS_OK.indexOf(tipo) < 0) throw new Error('Tipo de arquivo inválido: ' + tipo);
  var b64 = String(p.base64 || '');
  if (!b64) throw new Error('Arquivo vazio.');
  var bytes = Utilities.base64Decode(b64);
  var pasta = _pastaDemanda(id, true);
  var nome = tipo + '.xlsx';
  var blob = Utilities.newBlob(bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', nome);
  var arquivos = pasta.getFilesByName(nome);
  var antigos = [];
  while (arquivos.hasNext()) antigos.push(arquivos.next());
  if (antigos.length) antigos[0].setContent(blob);
  else pasta.createFile(blob);
  antigos.slice(1).forEach(function (f) { f.setTrashed(true); });

  var colunas = Array.isArray(p.colunas) ? p.colunas : [];
  var linhas = Array.isArray(p.linhas) ? p.linhas : [];
  var usarAba = p.usar_aba_rapida === true || p.usar_aba_rapida === 'SIM'
    || (p.usar_aba_rapida === undefined && colunas.length > 0 && linhas.length > 0 && !p.truncado);
  if (usarAba && colunas.length > 0 && !p.truncado) {
    _escreverAba(id, tipo, colunas, linhas);
  } else {
    // nunca deixa aba fantasma/antiga: Força fallback para o XLSX do Drive
    var antiga = _planilha().getSheetByName(_nomeAba(id, tipo));
    if (antiga) _planilha().deleteSheet(antiga);
  }

  _agremover(id);
  var d = _aba('DEMANDAS').getData().filter(function (x) { return String(x.id || '') === id; })[0];
  if (d) {
    d.atualizado_em = new Date().toISOString();
    _aba('DEMANDAS').salvar(d, 'id', id);
  }
  return _ok({ tipo: tipo, tamanho: bytes.length, aba_rapida: usarAba });
}

function _acaoArquivoLer(p) {
  var id = String(p.demanda_id || '').trim();
  var tipo = String(p.tipo || '').trim().toLowerCase();
  if (!_demandaArquivada(id)) {
    var rapido = _lerAba(id, tipo);
    if (rapido) return _ok({ colunas: rapido.colunas, linhas: rapido.linhas, origem: 'planilha' });
  }
  var pasta = _pastaDemanda(id, false);
  if (!pasta) throw new Error('Nenhum arquivo para esta demanda.');
  var arquivos = pasta.getFilesByName(tipo + '.xlsx');
  if (!arquivos.hasNext()) throw new Error('Arquivo ' + tipo + ' não enviado.');
  var bytes = arquivos.next().getBlob().getBytes();
  return _ok({ base64: Utilities.base64Encode(bytes), tipo: tipo });
}

/**
 * Le vários XLSX de uma demanda em UMA ÚNICA chamada (menos idas ao servidor).
 * Resposta: { ok:true, arquivos:{ pedidos:"base64", estoque:"base64", ... },
 *             erros:{ tipo:"mensagem" } }
 */
function _acaoArquivosLer(p) {
  var id = _idSeguro(p.demanda_id);
  var tipos = Array.isArray(p.tipos) && p.tipos.length ? p.tipos : TIPOS_OK.slice();
  tipos = tipos.map(function (t) { return String(t).trim().toLowerCase(); })
    .filter(function (t) { return TIPOS_OK.indexOf(t) >= 0; });
  if (!tipos.length) throw new Error('Nenhum tipo válido solicitado.');
  var arquivos = {};
  var erros = {};
  var arquivada = _demandaArquivada(id);
  tipos.forEach(function (tipo) {
    try {
      if (!arquivada) {
        var rapido = _lerAba(id, tipo);
        if (rapido) {
          arquivos[tipo] = { colunas: rapido.colunas, linhas: rapido.linhas, origem: 'planilha' };
          return;
        }
      }
      var pasta = _pastaDemanda(id, false);
      if (!pasta) throw new Error('Demanda sem arquivos enviados.');
      var it = pasta.getFilesByName(tipo + '.xlsx');
      if (!it.hasNext()) throw new Error('Arquivo ' + tipo + ' não enviado.');
      arquivos[tipo] = { base64: Utilities.base64Encode(it.next().getBlob().getBytes()), origem: 'drive' };
    } catch (erro) {
      erros[tipo] = String(erro && erro.message || erro);
    }
  });
  return _ok({ arquivos: arquivos, erros: erros });
}

/** Salva o resultado já processado da demanda (pré-agregação). */
function _extrairConfeccoesAgregado(dados) {
  var set = {};
  function add(v){ var s=String(v||'').trim(); if(s) set[s]=true; }
  (dados.cards || []).forEach(function(c){ add(c.confeccao || c['Confecção'] || c['Confeccao']); });
  (dados.pedidos || []).forEach(function(c){ add(c.confeccao || c['Confecção'] || c['Confecao']); });
  (dados.resumo_confeccao || []).forEach(function(c){ add(c.confeccao || c['Confecção'] || c['Confeccao'] || c.Grupo); });
  (dados.por_confeccao || []).forEach(function(c){ add(c.confeccao || c['Confecção'] || c.Grupo); });
  (dados.compra_resumo || []).forEach(function(c){ add(c.confeccao || c['Confecção'] || c['Confeccao']); });
  return Object.keys(set).sort(function(a,b){ return a.localeCompare(b); });
}

function _sincronizarCatalogoConfeccoes(confeccoes) {
  var aba = _aba('CATALOGO');
  var existentes = aba.getData();
  var tem = {};
  existentes.forEach(function(r){
    var c = String(r.confeccao || '').trim();
    if(c) tem[_normConf(c)] = true;
  });
  var ago = new Date().toISOString();
  var add = 0;
  (confeccoes||[]).forEach(function(conf){
    var nome = String(conf||'').trim();
    if(!nome) return;
    var k = _normConf(nome);
    if(tem[k]) return;
    var cod = '__CONF__' + k.replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'').toUpperCase();
    aba.salvar({ confeccao:nome, codigo:cod, item:'', tipo:'confecção', tamanho:'', marca:'', atualizado_em:ago }, 'codigo', cod);
    tem[k] = true; add++;
  });
  return add;
}

function _acaoAgregadoSalvar(p) {
  var demanda = String(p.demanda_id || '').trim();
  if (!demanda) throw new Error('Informe demanda_id.');
  var id = 'AGG-' + demanda;
  var dadosStr = String(p.dados_json || '{}');
  var dados = {};
  try { dados = JSON.parse(dadosStr) || {}; } catch(e) { dados = {}; }
  var confs = _extrairConfeccoesAgregado(dados);
  var confsNovas = _sincronizarCatalogoConfeccoes(confs);
  _aba('AGREGADOS').salvar({
    id: id,
    demanda_id: demanda,
    dados_json: dadosStr,
    atualizado_em: new Date().toISOString(),
    stamp: _stampDemanda(demanda)
  }, 'id', id);
  return _ok({ id: id, confeccoes: confs.length, confeccoes_novas: confsNovas });
}

function _acaoAgregadoLer(p) {
  var demanda = String(p.demanda_id || '').trim();
  var linhas = _aba('AGREGADOS').getData().filter(function (r) {
    return String(r.demanda_id || '') === demanda;
  });
  if (!linhas.length) throw new Error('Sem pré-agregação para esta demanda.');
  var stamp = String(linhas[0].stamp || '');
  var atual = _stampDemanda(demanda);
  if (stamp && atual && stamp !== atual) {
    throw new Error('Pré-agregação desatualizada.');
  }
  try {
    return _ok({ dados: JSON.parse(linhas[0].dados_json || '{}'),
                 atualizado_em: linhas[0].atualizado_em });
  } catch (e) {
    throw new Error('Pré-agregação inválida: ' + e.message);
  }
}

function _listarArquivos(id) {
  var pasta = _pastaDemanda(String(id || ''), false);
  if (!pasta) return [];
  var out = [];
  var files = pasta.getFiles();
  while (files.hasNext()) {
    var f = files.next();
    out.push({ nome: f.getName(), tamanho: f.getSize(), atualizado_em: f.getLastUpdated().toISOString() });
  }
  return out;
}

function _acaoUsuarioSalvar(p, user) {
  var usuario = String(p.usuario_alvo || p.usuario || '').trim().toLowerCase();
  var senhaNova = p.senha_nova !== undefined ? String(p.senha_nova || '') : String(p.senha || '');
  if (!usuario) throw new Error('Informe o usuário.');
  var registro = {
    usuario: usuario,
    senha_sha: senhaNova ? _sha(usuario + ':' + senhaNova) : (p.senha_sha || ''),
    nome: String(p.nome || '').trim(),
    admin: p.admin ? 'SIM' : 'NAO',
    ativo: p.ativo === false ? 'NAO' : 'SIM'
  };
  var existente = _aba('USUARIOS').getData().filter(function (u) { return u && String(u.usuario || '') === usuario; })[0] || null;
  if (!senhaNova && existente) registro.senha_sha = existente.senha_sha;
  if (existente && _ehAdmin(user) &&
      String(user.usuario || '').toLowerCase() === usuario && !p.admin) {
    throw new Error('Você não pode remover o próprio acesso de administrador.');
  }
  _aba('USUARIOS').salvar(registro, 'usuario', usuario);
  return _ok({ usuario: usuario });
}

function _acaoPermissaoSalvar(p) {
  var usuario = String(p.usuario_alvo || p.usuario || '').trim().toLowerCase();
  var pagina = String(p.pagina || '').trim();
  var nivel = String(p.nivel || 'visualizacao').trim().toLowerCase();
  if (!usuario || !pagina) throw new Error('Informe usuário e página.');
  var id = usuario + '|' + pagina;
  var abaPerm = _aba('PERMISSOES');
  abaPerm.excluir('id', id);
  abaPerm.salvar({ id: id, usuario: usuario, pagina: pagina, nivel: nivel }, 'id', id);
  return _ok({ usuario: usuario, pagina: pagina, nivel: nivel });
}

function _acaoCatalogoSalvar(p) {
  var itens = p.itens || [];
  if (!Array.isArray(itens)) throw new Error('Lista de itens inválida.');
  var ago = new Date().toISOString();
  itens.forEach(function (it) {
    var chave = String(it.codigo || '').trim();
    if (!chave) return;
    _aba('CATALOGO').salvar({
      confeccao: String(it.confeccao || '').trim(),
      codigo: chave,
      item: String(it.item || '').trim(),
      tipo: String(it.tipo || '').trim(),
      tamanho: String(it.tamanho || '').trim(),
      marca: String(it.marca || '').trim(),
      atualizado_em: ago
    }, 'codigo', chave);
  });
  return _ok({ salvos: itens.length });
}

function _acaoCatalogoExcluir(p) {
  _aba('CATALOGO').excluir('codigo', String(p.codigo || ''));
  return _ok({});
}

function _acaoAnaliseSalvar(p, user) {
  var id = String(p.id || '').trim() || _novoId('ANA');
  _aba('ANALISES').salvar({
    id: id,
    demanda_id: String(p.demanda_id || '').trim(),
    nome: String(p.nome || '').trim(),
    criado_em: new Date().toISOString(),
    dados_json: String(p.dados_json || '{}'),
    usuario: String((user || {}).usuario || '')
  }, 'id', id);
  return _ok({ id: id });
}

function _acaoAnaliseExcluir(p, user) {
  var id = String(p.id || '').trim();
  var alvo = _aba('ANALISES').getData().filter(function (a) { return String(a.id || '') === id; })[0] || {};
  if (!_ehAdmin(user) &&
      String(alvo.usuario || '').toLowerCase() !== String((user || {}).usuario || '').toLowerCase()) {
    throw new Error('Permissão negada: análise de outro usuário.');
  }
  _aba('ANALISES').excluir('id', id);
  return _ok({});
}
