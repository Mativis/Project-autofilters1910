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
 *   DEMANDAS   - id, nome, fonte, criado_em, atualizado_em
 *   CATALOGO   - confeccao, codigo, item, tipo, tamanho, marca, atualizado_em
 *   ANALISES   - id, demanda_id, nome, criado_em, dados_json
 *
 * Os XLSX ficam no Google Drive, em VisualfilCloud/<id da demanda>/<tipo>.xlsx
 */

var VF_VERSAO = '1.0.0';
var VF_PASTA = 'VisualfilCloud';

function doPost(e) {
  try {
    var p = e && e.postData && e.postData.contents ? JSON.parse(e.postData.contents) : {};
    var acao = String(p.action || '').toLowerCase();
    var usuario = String(p.usuario || p.user || '').trim();
    var senha = String(p.senha || '').trim();

    if (acao === 'ping') return _ok({ versao: VF_VERSAO, hora: new Date().toISOString() });
    if (acao === 'inicializar') return _acaoInicializar(p);
    if (acao === 'login') return _acaoLogin(usuario, senha);

    // Demais ações exigem login
    var user = _autenticar(usuario, senha);
    if (!user) throw new Error('Usuário ou senha inválidos.');

    switch (acao) {
      case 'demandas_listar': return _ok({ demandas: _aba('DEMANDAS').getData() });
      case 'demanda_salvar': return _admin(user), _acaoDemandaSalvar(p);
      case 'demanda_excluir': return _admin(user), _acaoDemandaExcluir(p);
      case 'arquivo_salvar': return _admin(user), _acaoArquivoSalvar(p);
      case 'arquivo_ler': return _acaoArquivoLer(p);
      case 'arquivos_listar': return _ok({ arquivos: _listarArquivos(p.demanda_id) });
      case 'usuarios_listar': return _admin(user), _ok({ usuarios: _aba('USUARIOS').getData() });
      case 'usuario_salvar': return _admin(user), _acaoUsuarioSalvar(p);
      case 'permissoes_listar': return _ok({ permissoes: _aba('PERMISSOES').getData() });
      case 'permissao_salvar': return _admin(user), _acaoPermissaoSalvar(p);
      case 'catalogo_listar': return _ok({ catalogo: _aba('CATALOGO').getData() });
      case 'catalogo_salvar': return _admin(user), _acaoCatalogoSalvar(p);
      case 'catalogo_excluir': return _admin(user), _acaoCatalogoExcluir(p);
      case 'analise_salvar': return _acaoAnaliseSalvar(p, user);
      case 'analises_listar': return _ok({ analises: _aba('ANALISES').getData() });
      case 'analise_excluir': return _admin(user), _acaoAnaliseExcluir(p);
      default: throw new Error('Ação desconhecida: ' + acao);
    }
  } catch (erro) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, erro: String(erro && erro.message || erro) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({ ok: true, versao: VF_VERSAO, nome: 'Visualfil Cloud API' }))
    .setMimeType(ContentService.MimeType.JSON);
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

function _planilha() { return SpreadsheetApp.getActiveSpreadsheet(); }

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
    getData: function () {
      if (sh.getLastRow() < 2) return [];
      var cols = Math.max(1, sh.getLastColumn());
      var vals = sh.getRange(2, 1, sh.getLastRow() - 1, cols).getValues();
      var head = this.cabecalhos();
      return vals
        .filter(function (row) { return row.some(function (v) { return String(v || '').trim() !== ''; }); })
        .map(function (row) {
          var o = {};
          head.forEach(function (h, i) { if (h) o[h] = row[i]; });
          return o;
        });
    },
    salvar: function (registro, chave, valor) {
      var head = this.cabecalhos();
      var linha = this.getData();
      var idx = -1;
      for (var i = 0; i < linha.length; i++) {
        if (String(linha[i][chave] || '') === String(valor || '')) { idx = i; break; }
      }
      var nova = head.map(function (h) { return registro[h] === undefined ? '' : registro[h]; });
      if (idx >= 0) sh.getRange(idx + 2, 1, 1, head.length).setValues([nova]);
      else sh.appendRow(nova);
    },
    excluir: function (chave, valor) {
      var dados = this.getData();
      for (var i = dados.length - 1; i >= 0; i--) {
        if (String(dados[i][chave] || '') === String(valor || '')) sh.deleteRow(i + 2);
      }
    }
  };
}

function _garantirCabecalhos(nome, head) {
  var sh = _planilha().getSheetByName(nome) || _planilha().insertSheet(nome);
  if (sh.getLastRow() < 1) sh.getRange(1, 1, 1, head.length).setValues([head]);
}

function _admin(user) {
  if (String(user.admin || '').toUpperCase() !== 'SIM' && String(user.admin || '') !== 'true') {
    throw new Error('Permissão negada: somente administrador.');
  }
}

function _autenticar(usuario, senha) {
  if (!usuario || !senha) return null;
  var hash = _sha(usuario.toLowerCase() + ':' + senha);
  var users = _aba('USUARIOS').getData();
  for (var i = 0; i < users.length; i++) {
    var u = users[i];
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
  _garantirCabecalhos('DEMANDAS', ['id', 'nome', 'fonte', 'criado_em', 'atualizado_em']);
  _garantirCabecalhos('CATALOGO', ['confeccao', 'codigo', 'item', 'tipo', 'tamanho', 'marca', 'atualizado_em']);
  _garantirCabecalhos('ANALISES', ['id', 'demanda_id', 'nome', 'criado_em', 'dados_json']);

  var adminUser = String(p.usuario || 'admin').trim();
  var adminSenha = String(p.senha || 'admin').trim();
  var users = _aba('USUARIOS').getData();
  var existe = users.some(function (u) { return String(u.usuario || '') === adminUser; });
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
  _aba('DEMANDAS').salvar({
    id: id,
    nome: String(p.nome || '').trim(),
    fonte: String(p.fonte || p.remessa || '').trim(),
    criado_em: atual.criado_em || ago,
    atualizado_em: ago
  }, 'id', id);
  return _ok({ id: id });
}

function _acaoDemandaExcluir(p) {
  var id = String(p.id || '').trim();
  if (!id) throw new Error('Informe o id da demanda.');
  _aba('DEMANDAS').excluir('id', id);
  // remove arquivos da pasta
  var pasta = _pastaDemanda(id, false);
  if (pasta) {
    var files = pasta.getFiles();
    while (files.hasNext()) files.next().setTrashed(true);
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

var TIPOS_OK = ['pedidos', 'estoque', 'producao', 'projecao'];

function _acaoArquivoSalvar(p) {
  var id = String(p.demanda_id || '').trim();
  var tipo = String(p.tipo || '').trim().toLowerCase();
  if (TIPOS_OK.indexOf(tipo) < 0) throw new Error('Tipo de arquivo inválido: ' + tipo);
  var b64 = String(p.base64 || '');
  if (!b64) throw new Error('Arquivo vazio.');
  var bytes = Utilities.base64Decode(b64);
  var pasta = _pastaDemanda(id, true);
  var nome = tipo + '.xlsx';
  var arquivos = pasta.getFilesByName(nome);
  var blob = Utilities.newBlob(bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', nome);
  if (arquivos.hasNext()) arquivos.next().setContent(blob);
  else pasta.createFile(blob);

  // atualiza stamp da demanda
  var d = _aba('DEMANDAS').getData().filter(function (x) { return String(x.id || '') === id; })[0];
  if (d) {
    d.atualizado_em = new Date().toISOString();
    _aba('DEMANDAS').salvar(d, 'id', id);
  }
  return _ok({ tipo: tipo, tamanho: bytes.length });
}

function _acaoArquivoLer(p) {
  var id = String(p.demanda_id || '').trim();
  var tipo = String(p.tipo || '').trim().toLowerCase();
  var pasta = _pastaDemanda(id, false);
  if (!pasta) throw new Error('Nenhum arquivo para esta demanda.');
  var arquivos = pasta.getFilesByName(tipo + '.xlsx');
  if (!arquivos.hasNext()) throw new Error('Arquivo ' + tipo + ' não enviado.');
  var bytes = arquivos.next().getBlob().getBytes();
  return _ok({ base64: Utilities.base64Encode(bytes), tipo: tipo });
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

function _acaoUsuarioSalvar(p) {
  var usuario = String(p.usuario || '').trim().toLowerCase();
  if (!usuario) throw new Error('Informe o usuário.');
  var registro = {
    usuario: usuario,
    senha_sha: p.senha ? _sha(usuario + ':' + String(p.senha)) : (p.senha_sha || ''),
    nome: String(p.nome || '').trim(),
    admin: p.admin ? 'SIM' : 'NAO',
    ativo: p.ativo === false ? 'NAO' : 'SIM'
  };
  var existente = _aba('USUARIOS').getData().filter(function (u) { return String(u.usuario || '') === usuario; })[0];
  if (!p.senha && existente) registro.senha_sha = existente.senha_sha;
  _aba('USUARIOS').salvar(registro, 'usuario', usuario);
  return _ok({ usuario: usuario });
}

function _acaoPermissaoSalvar(p) {
  var usuario = String(p.usuario || '').trim().toLowerCase();
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
    dados_json: String(p.dados_json || '{}')
  }, 'id', id);
  return _ok({ id: id });
}

function _acaoAnaliseExcluir(p) {
  _aba('ANALISES').excluir('id', String(p.id || ''));
  return _ok({});
}
