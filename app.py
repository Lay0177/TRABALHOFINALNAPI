from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

app = Flask(__name__)
app.secret_key = 'mentalnapi_secret_key_2026'

# ==========================================
# CONFIGURAÇÃO
# ==========================================
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'email_remetente': 'mentalnapi.suporte@gmail.com',
    'email_senha': 'myfasylkrjttpqyd',
    'email_destino': 'layaneraissatabletinfo@gmail.com'
}

# Permite acesso à session nos templates
@app.context_processor
def inject_session():
    return dict(session=session)


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def salvar_usuario_json(nome, usuario, senha, casa, data_cadastro):
    try:
        novo_usuario = {
            'nome': nome,
            'usuario': usuario,
            'senha': senha,
            'casa': casa,
            'data_cadastro': data_cadastro
        }

        if os.path.exists('usuarios.json'):
            with open('usuarios.json', 'r', encoding='utf-8') as f:
                try:
                    dados = json.load(f)
                    if isinstance(dados, dict) and 'usuarios' in dados:
                        usuarios = dados['usuarios']
                    else:
                        usuarios = dados if isinstance(dados, list) else []
                except json.JSONDecodeError:
                    usuarios = []
        else:
            usuarios = []

        for u in usuarios:
            if u.get('usuario') == usuario:
                return False, "Usuário já existe!"

        usuarios.append(novo_usuario)
        with open('usuarios.json', 'w', encoding='utf-8') as f:
            json.dump({'usuarios': usuarios}, f, ensure_ascii=False, indent=2)

        return True, "Usuário salvo com sucesso!"

    except Exception as e:
        print(f"Erro ao salvar no JSON: {str(e)}")
        return False, f"Erro ao salvar no JSON: {str(e)}"


def ler_usuarios_json():
    try:
        if os.path.exists('usuarios.json'):
            with open('usuarios.json', 'r', encoding='utf-8') as f:
                dados = json.load(f)
                if isinstance(dados, dict) and 'usuarios' in dados:
                    return dados['usuarios']
                elif isinstance(dados, list):
                    return dados
        return []
    except Exception as e:
        print(f"Erro ao ler JSON: {str(e)}")
        return []


def get_db_connection():
    conn = sqlite3.connect('mentalnapi.db')
    conn.row_factory = sqlite3.Row
    return conn


# ==========================================
# INICIALIZAÇÃO DO BANCO
# ==========================================
def init_db():
    conn = sqlite3.connect('mentalnapi.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            casa TEXT NOT NULL,
            data_cadastro TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS psicologas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            crp TEXT NOT NULL,
            especialidade TEXT NOT NULL,
            unidade TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS horarios_psicologas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            psicologa_id INTEGER NOT NULL,
            dia_semana INTEGER NOT NULL,
            horario TEXT NOT NULL,
            FOREIGN KEY (psicologa_id) REFERENCES psicologas(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            psicologa_id INTEGER NOT NULL,
            unidade TEXT NOT NULL,
            data TEXT NOT NULL,
            horario TEXT NOT NULL,
            modalidade TEXT NOT NULL,
            status TEXT DEFAULT 'Agendado',
            observacoes TEXT,
            data_criacao TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (psicologa_id) REFERENCES psicologas(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            psicologa_id INTEGER NOT NULL,
            mensagem TEXT NOT NULL,
            remetente TEXT NOT NULL,
            data_envio TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (psicologa_id) REFERENCES psicologas(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS mensagens_contato (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            telefone TEXT,
            assunto TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            status TEXT DEFAULT 'Nao lida',
            data_envio TEXT NOT NULL,
            usuario_id INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS psicologas_login (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            psicologa_id INTEGER NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            FOREIGN KEY (psicologa_id) REFERENCES psicologas(id)
        )
    ''')

    # Corrige nome antigo
    c.execute("UPDATE psicologas SET nome = 'Luara' WHERE nome = 'Yara'")

    # Insere psicólogas se a tabela estiver vazia
    c.execute("SELECT COUNT(*) FROM psicologas")
    if c.fetchone()[0] == 0:
        psicologas = [
            ('Barbara', 'CRP 12/34567', 'Psicopedagoga - Especialista em adolescentes', 'Unidade Natal-zn'),
            ('Carol', 'CRP 12/34568', 'Psicopedagoga - Foco em inclusao escolar', 'Unidade Natal-zn'),
            ('Evandilson', 'CRP 12/34569', 'Psicopedagogo - Acompanhamento de jovens', 'Unidade Mossoro'),
            ('Luara', 'CRP 12/34570', 'Psicologa - Saude mental e bem-estar', 'Unidade Mossoro')
        ]
        c.executemany(
            'INSERT INTO psicologas (nome, crp, especialidade, unidade) VALUES (?, ?, ?, ?)',
            psicologas
        )

        horarios = [
            (1, 1, '08:00'), (1, 1, '09:00'), (1, 1, '10:00'),
            (1, 2, '08:00'), (1, 2, '09:00'), (1, 2, '10:00'),
            (1, 4, '14:00'), (1, 4, '15:00'), (1, 4, '16:00'),
            (2, 1, '14:00'), (2, 1, '15:00'), (2, 1, '16:00'),
            (2, 2, '14:00'), (2, 2, '15:00'), (2, 2, '16:00'),
            (2, 5, '08:00'), (2, 5, '09:00'), (2, 5, '10:00'),
            (3, 1, '08:00'), (3, 1, '09:00'), (3, 1, '10:00'),
            (3, 3, '08:00'), (3, 3, '09:00'), (3, 3, '10:00'),
            (3, 5, '14:00'), (3, 5, '15:00'), (3, 5, '16:00'),
            (4, 2, '14:00'), (4, 2, '15:00'), (4, 2, '16:00'),
            (4, 4, '14:00'), (4, 4, '15:00'), (4, 4, '16:00'),
            (4, 6, '08:00'), (4, 6, '09:00'), (4, 6, '10:00')
        ]
        c.executemany(
            'INSERT INTO horarios_psicologas (psicologa_id, dia_semana, horario) VALUES (?, ?, ?)',
            horarios
        )

    # Insere ou atualiza logins dos psicólogos
    c.execute("SELECT id, nome FROM psicologas")
    mapa = {row[1].lower(): row[0] for row in c.fetchall()}

    logins = [
        ('barbara', 'barbara123'),
        ('carol', 'carol123'),
        ('evandilson', 'evandilson123'),
        ('luara', 'luara123')
    ]

    for user, senha in logins:
        if user in mapa:
            p_id = mapa[user]
            c.execute("SELECT id FROM psicologas_login WHERE usuario = ?", (user,))
            if c.fetchone():
                c.execute(
                    "UPDATE psicologas_login SET psicologa_id = ?, senha = ? WHERE usuario = ?",
                    (p_id, senha, user)
                )
            else:
                c.execute(
                    "INSERT INTO psicologas_login (psicologa_id, usuario, senha) VALUES (?, ?, ?)",
                    (p_id, user, senha)
                )

    conn.commit()
    conn.close()


# ==========================================
# E-MAIL
# ==========================================
def enviar_email_contato(nome, email, telefone, assunto, mensagem):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email_remetente']
        msg['To'] = EMAIL_CONFIG['email_destino']
        msg['Subject'] = f"[MENTALNAPI] Contato - {assunto}"

        corpo = f"""
        <html><body style="font-family:Arial">
            <h2>Nova mensagem de contato</h2>
            <p><b>Nome:</b> {nome}</p>
            <p><b>Email:</b> {email}</p>
            <p><b>Telefone:</b> {telefone or 'Não informado'}</p>
            <p><b>Assunto:</b> {assunto}</p>
            <p><b>Mensagem:</b><br>{mensagem.replace(chr(10), '<br>')}</p>
            <hr><small>Enviado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
        </body></html>
        """
        msg.attach(MIMEText(corpo, 'html'))

        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['email_remetente'], EMAIL_CONFIG['email_senha'])
            server.send_message(msg)

        enviar_email_confirmacao(nome, email)
        return True, "Email enviado com sucesso!"
    except Exception as e:
        print(f"Erro ao enviar email: {str(e)}")
        return False, f"Erro ao enviar email: {str(e)}"


def enviar_email_confirmacao(nome, email_destino):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email_remetente']
        msg['To'] = email_destino
        msg['Subject'] = "MentalNapi - Recebemos sua mensagem"

        corpo = f"""
        <html><body style="font-family:Arial">
            <h2>Mensagem recebida</h2>
            <p>Olá <b>{nome}</b>,</p>
            <p>Recebemos sua mensagem e em breve entraremos em contato.</p>
            <p>Atenciosamente,<br><b>Equipe MentalNapi</b></p>
        </body></html>
        """
        msg.attach(MIMEText(corpo, 'html'))

        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['email_remetente'], EMAIL_CONFIG['email_senha'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Erro email confirmação: {str(e)}")
        return False


# ==========================================
# ROTAS PÚBLICAS / USUÁRIO
# ==========================================
@app.route('/')
def inicio():
    return render_template('inicio.html')


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/logar', methods=['GET', 'POST'])
def logar():
    if request.method == 'POST':
        usuario = request.form.get('username')
        senha = request.form.get('password')
        casa = request.form.get('casa')

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM usuarios WHERE usuario = ? AND casa = ?',
            (usuario, casa)
        ).fetchone()
        conn.close()

        if user and user['senha'] == senha:
            session['usuario_logado'] = True
            session['usuario_id'] = user['id']
            session['usuario_nome'] = user['nome']
            session['usuario_casa'] = user['casa']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('menu'))

        flash('Usuário, senha ou unidade incorretos.', 'danger')

    return render_template('log.html')


@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if request.method == 'POST':
        nome = request.form.get('nome')
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        casa = request.form.get('casa')
        data_cadastro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        existe = conn.execute('SELECT id FROM usuarios WHERE usuario = ?', (usuario,)).fetchone()
        if existe:
            flash('Usuário já cadastrado.', 'danger')
            conn.close()
            return render_template('cadastro.html')

        try:
            conn.execute(
                'INSERT INTO usuarios (nome, usuario, senha, casa, data_cadastro) VALUES (?, ?, ?, ?, ?)',
                (nome, usuario, senha, casa, data_cadastro)
            )
            conn.commit()
            salvar_usuario_json(nome, usuario, senha, casa, data_cadastro)
            flash('Cadastro realizado com sucesso!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Erro ao cadastrar: {str(e)}', 'danger')
            conn.close()
            return render_template('cadastro.html')

        conn.close()
        return redirect(url_for('logar'))

    return render_template('cadastro.html')


@app.route('/logout')
def logout():
    for k in ('usuario_logado', 'usuario_id', 'usuario_nome', 'usuario_casa'):
        session.pop(k, None)
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('inicio'))


@app.route('/menu')
def menu():
    if not session.get('usuario_logado'):
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    agendamentos = conn.execute('''
        SELECT a.*, p.nome AS psicologa_nome
        FROM agendamentos a
        JOIN psicologas p ON a.psicologa_id = p.id
        WHERE a.usuario_id = ? AND a.status = 'Agendado'
        ORDER BY a.data ASC, a.horario ASC
    ''', (session['usuario_id'],)).fetchall()
    conn.close()

    return render_template('menu.html', agendamentos=agendamentos)


@app.route('/unidades')
def unidades():
    if not session.get('usuario_logado'):
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    unidade_selecionada = request.args.get('unidade', 'Unidade Natal-zn')
    unidades_map = {
        'Unidade Natal-zn': 'Natal - Zona Norte',
        'Unidade Mossoro': 'Mossoró'
    }

    conn = get_db_connection()
    psicologas = conn.execute('''
        SELECT p.*, GROUP_CONCAT(h.horario) AS horarios
        FROM psicologas p
        LEFT JOIN horarios_psicologas h ON p.id = h.psicologa_id
        WHERE p.unidade = ?
        GROUP BY p.id
    ''', (unidade_selecionada,)).fetchall()

    lista = []
    for p in psicologas:
        horarios = p['horarios'].split(',') if p['horarios'] else []
        lista.append({
            'id': p['id'],
            'nome': p['nome'],
            'crp': p['crp'],
            'especialidade': p['especialidade'],
            'unidade': p['unidade'],
            'horarios': horarios[:3] if horarios else ['Sem horários']
        })
    conn.close()

    return render_template('unidades.html',
                           unidades=unidades_map,
                           unidade_atual=unidade_selecionada,
                           psicologas=lista)


@app.route('/agendar_direto')
def agendar_direto():
    if not session.get('usuario_logado'):
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))
    return redirect(url_for('unidades', unidade=session.get('usuario_casa', 'Unidade Natal-zn')))


@app.route('/meus_agendamentos')
def meus_agendamentos():
    if not session.get('usuario_logado'):
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    agendamentos = conn.execute('''
        SELECT a.*, p.nome AS psicologa_nome
        FROM agendamentos a
        JOIN psicologas p ON a.psicologa_id = p.id
        WHERE a.usuario_id = ? AND a.status = 'Agendado'
        ORDER BY a.data ASC, a.horario ASC
    ''', (session['usuario_id'],)).fetchall()
    conn.close()

    return render_template('meus_agendamentos.html', agendamentos=agendamentos)


@app.route('/historico')
def historico():
    if not session.get('usuario_logado'):
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    consultas = conn.execute('''
        SELECT a.*, p.nome AS psicologa_nome
        FROM agendamentos a
        JOIN psicologas p ON a.psicologa_id = p.id
        WHERE a.usuario_id = ?
        ORDER BY a.data DESC, a.horario DESC
    ''', (session['usuario_id'],)).fetchall()

    chats = conn.execute('''
        SELECT c.psicologa_id, p.nome AS psicologa_nome,
               COUNT(c.id) AS total_mensagens,
               MAX(c.data_envio) AS ultima_mensagem
        FROM chats c
        JOIN psicologas p ON c.psicologa_id = p.id
        WHERE c.usuario_id = ?
        GROUP BY c.psicologa_id
        ORDER BY ultima_mensagem DESC
    ''', (session['usuario_id'],)).fetchall()
    conn.close()

    return render_template('historico.html', consultas=consultas, chats=chats)


@app.route('/chats')
def chats():
    if not session.get('usuario_logado'):
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    psicologas = conn.execute('''
        SELECT DISTINCT p.*
        FROM psicologas p
        INNER JOIN agendamentos a ON p.id = a.psicologa_id
        WHERE a.usuario_id = ? AND a.status = 'Agendado' AND a.modalidade = 'Online'
        ORDER BY p.nome ASC
    ''', (session['usuario_id'],)).fetchall()

    chat_psicologas = [r['psicologa_id'] for r in conn.execute(
        'SELECT DISTINCT psicologa_id FROM chats WHERE usuario_id = ?',
        (session['usuario_id'],)
    ).fetchall()]

    agendamentos_dict = {}
    for p in psicologas:
        ag = conn.execute('''
            SELECT id, data, horario, modalidade, status, observacoes
            FROM agendamentos
            WHERE usuario_id = ? AND psicologa_id = ?
              AND status = 'Agendado' AND modalidade = 'Online'
            ORDER BY data ASC, horario ASC LIMIT 1
        ''', (session['usuario_id'], p['id'])).fetchone()
        if ag:
            agendamentos_dict[p['id']] = dict(ag)

    conn.close()
    return render_template('chats.html',
                           psicologas=psicologas,
                           chat_psicologas=chat_psicologas,
                           agendamentos=agendamentos_dict)


@app.route('/chat/<int:psicologa_id>')
def chat(psicologa_id):
    if not session.get('usuario_logado'):
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    psicologa = conn.execute('SELECT * FROM psicologas WHERE id = ?', (psicologa_id,)).fetchone()
    mensagens = conn.execute('''
        SELECT * FROM chats WHERE usuario_id = ? AND psicologa_id = ?
        ORDER BY data_envio ASC
    ''', (session['usuario_id'], psicologa_id)).fetchall()
    conn.close()

    if not psicologa:
        flash('Psicóloga não encontrada.', 'danger')
        return redirect(url_for('unidades'))

    return render_template('chat_detalhe.html', psicologa=psicologa, mensagens=mensagens)


@app.route('/enviar_mensagem', methods=['POST'])
def enviar_mensagem():
    if not session.get('usuario_logado'):
        return {'erro': 'Não autorizado'}, 401

    psicologa_id = request.form.get('psicologa_id')
    mensagem = request.form.get('mensagem')

    if not mensagem or not mensagem.strip():
        flash('Digite uma mensagem.', 'warning')
        return redirect(url_for('chat', psicologa_id=psicologa_id))

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO chats (usuario_id, psicologa_id, mensagem, remetente, data_envio)
        VALUES (?, ?, ?, ?, ?)
    ''', (session['usuario_id'], psicologa_id, mensagem, 'Usuario',
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

    flash('Mensagem enviada!', 'success')
    return redirect(url_for('chat', psicologa_id=psicologa_id))


@app.route('/cancelar_agendamento/<int:agendamento_id>', methods=['POST'])
def cancelar_agendamento(agendamento_id):
    if not session.get('usuario_logado'):
        flash('Faça login.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    ag = conn.execute(
        'SELECT * FROM agendamentos WHERE id = ? AND usuario_id = ?',
        (agendamento_id, session['usuario_id'])
    ).fetchone()

    if not ag:
        flash('Agendamento não encontrado.', 'danger')
        conn.close()
        return redirect(url_for('meus_agendamentos'))

    conn.execute('UPDATE agendamentos SET status = ? WHERE id = ?', ('Cancelado', agendamento_id))
    conn.commit()
    conn.close()

    flash('Agendamento cancelado com sucesso!', 'success')
    return redirect(url_for('meus_agendamentos'))


@app.route('/agendar', methods=['POST'])
def agendar():
    if not session.get('usuario_logado'):
        flash('Faça login.', 'warning')
        return redirect(url_for('login'))

    unidade = request.form.get('unidade')
    psicologa_nome = request.form.get('psicologa')
    data = request.form.get('data')
    horario = request.form.get('horario')
    modalidade = request.form.get('modalidade')
    observacoes = request.form.get('observacoes', '')

    if not all([unidade, psicologa_nome, data, horario, modalidade]):
        flash('Preencha todos os campos obrigatórios.', 'danger')
        return redirect(url_for('menu'))

    conn = get_db_connection()
    psi = conn.execute(
        'SELECT id FROM psicologas WHERE nome = ? AND unidade = ?',
        (psicologa_nome, unidade)
    ).fetchone()

    if not psi:
        flash('Psicóloga não encontrada.', 'danger')
        conn.close()
        return redirect(url_for('menu'))

    existe = conn.execute('''
        SELECT id FROM agendamentos
        WHERE psicologa_id = ? AND data = ? AND horario = ? AND status = 'Agendado'
    ''', (psi['id'], data, horario)).fetchone()

    if existe:
        flash('Este horário já está ocupado.', 'danger')
        conn.close()
        return redirect(url_for('menu'))

    conn.execute('''
        INSERT INTO agendamentos
        (usuario_id, psicologa_id, unidade, data, horario, modalidade, status, observacoes, data_criacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (session['usuario_id'], psi['id'], unidade, data, horario,
          modalidade, 'Agendado', observacoes,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

    flash('Agendamento realizado com sucesso!', 'success')
    return redirect(url_for('meus_agendamentos'))


@app.route('/sobre')
def sobre():
    return render_template('sobre.html')


@app.route('/contato')
def contato():
    return render_template('contato.html')


@app.route('/enviar_contato', methods=['POST'])
def enviar_contato():
    nome = request.form.get('nome')
    email = request.form.get('email')
    telefone = request.form.get('telefone')
    assunto = request.form.get('assunto')
    mensagem = request.form.get('mensagem')

    if not all([nome, email, assunto, mensagem]):
        flash('Preencha todos os campos obrigatórios.', 'danger')
        return redirect(url_for('contato'))

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO mensagens_contato
        (nome, email, telefone, assunto, mensagem, status, data_envio, usuario_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (nome, email, telefone, assunto, mensagem, 'Nao lida',
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          session.get('usuario_id')))
    conn.commit()
    conn.close()

    sucesso, _ = enviar_email_contato(nome, email, telefone, assunto, mensagem)
    if sucesso:
        flash('Mensagem enviada! Entraremos em contato em breve.', 'success')
    else:
        flash('Mensagem salva no sistema, mas houve erro ao enviar email.', 'warning')

    return redirect(url_for('contato'))


@app.route('/admin/mensagens')
def admin_mensagens():
    if not session.get('usuario_logado'):
        flash('Faça login primeiro.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    mensagens = conn.execute('''
        SELECT m.*, u.nome AS usuario_nome
        FROM mensagens_contato m
        LEFT JOIN usuarios u ON m.usuario_id = u.id
        ORDER BY m.data_envio DESC
    ''').fetchall()
    total = conn.execute('SELECT COUNT(*) FROM mensagens_contato').fetchone()[0]
    nao_lidas = conn.execute(
        "SELECT COUNT(*) FROM mensagens_contato WHERE status = 'Nao lida'"
    ).fetchone()[0]
    conn.close()

    return render_template('admin_mensagens.html',
                           mensagens=mensagens, total=total, nao_lidas=nao_lidas)


@app.route('/admin/mensagem/<int:mensagem_id>/status', methods=['POST'])
def atualizar_status_mensagem(mensagem_id):
    if not session.get('usuario_logado'):
        flash('Faça login.', 'warning')
        return redirect(url_for('login'))

    novo = request.form.get('status')
    if novo not in ['Nao lida', 'Lida', 'Respondida']:
        flash('Status inválido.', 'danger')
        return redirect(url_for('admin_mensagens'))

    conn = get_db_connection()
    conn.execute('UPDATE mensagens_contato SET status = ? WHERE id = ?', (novo, mensagem_id))
    conn.commit()
    conn.close()

    flash('Status atualizado!', 'success')
    return redirect(url_for('admin_mensagens'))


@app.route('/ver_sessao')
def ver_sessao():
    return {
        'usuario_logado': session.get('usuario_logado'),
        'usuario_id': session.get('usuario_id'),
        'usuario_nome': session.get('usuario_nome'),
        'usuario_casa': session.get('usuario_casa'),
        'psicologo_logado': session.get('psicologo_logado'),
        'psicologo_id': session.get('psicologo_id'),
        'psicologo_nome': session.get('psicologo_nome'),
        'psicologo_crp': session.get('psicologo_crp')
    }


# ==========================================
# ROTAS DO PSICÓLOGO (PAINEL PROFISSIONAL)
# ==========================================
@app.route('/login_psicologo', methods=['GET', 'POST'])
def login_psicologo():
    if request.method == 'POST':
        usuario = (request.form.get('username') or '').strip().lower()
        senha = request.form.get('password') or ''

        conn = get_db_connection()
        user = conn.execute('''
            SELECT pl.*, p.nome, p.crp
            FROM psicologas_login pl
            JOIN psicologas p ON pl.psicologa_id = p.id
            WHERE pl.usuario = ?
        ''', (usuario,)).fetchone()

        if not user:
            conn.close()
            flash('Usuário não encontrado no sistema.', 'danger')
            return render_template('login_psicologo.html')

        if user['senha'] != senha:
            conn.close()
            flash('Senha incorreta. Tente novamente.', 'danger')
            return render_template('login_psicologo.html')

        session['psicologo_logado'] = True
        session['psicologo_id'] = user['psicologa_id']
        session['psicologo_nome'] = user['nome']
        session['psicologo_crp'] = user['crp']
        conn.close()

        flash(f'Bem-vindo(a), {user["nome"]}!', 'success')
        return redirect(url_for('painel_psicologo'))

    return render_template('login_psicologo.html')


@app.route('/painel_psicologo')
def painel_psicologo():
    if not session.get('psicologo_logado'):
        flash('Faça login como profissional.', 'warning')
        return redirect(url_for('login_psicologo'))

    conn = get_db_connection()
    agendamentos = conn.execute('''
        SELECT a.*, u.nome AS paciente_nome
        FROM agendamentos a
        JOIN usuarios u ON a.usuario_id = u.id
        WHERE a.psicologa_id = ? AND a.status = 'Agendado'
        ORDER BY a.data ASC, a.horario ASC
    ''', (session['psicologo_id'],)).fetchall()
    conn.close()

    return render_template('Psitela.html', agendamentos=agendamentos)


@app.route('/logout_psicologo')
def logout_psicologo():
    for k in ('psicologo_logado', 'psicologo_id', 'psicologo_nome', 'psicologo_crp'):
        session.pop(k, None)
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('inicio'))


# ==========================================
# INICIALIZAÇÃO — RODA SEMPRE
# ==========================================
init_db()

if __name__ == '__main__':
    print("=" * 50)
    print("MentalNapi iniciado")
    print("Usuário:    http://127.0.0.1:5000/")
    print("Psicólogo:  http://127.0.0.1:5000/login_psicologo")
    print("=" * 50)
    app.run(debug=True)