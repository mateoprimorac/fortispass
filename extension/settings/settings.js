'use strict';

// ─────────────────────────────────────────────────────────────────────────────
// NAV — registered first, before anything else, so buttons always work
// ─────────────────────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    const sec = document.getElementById('section-' + btn.dataset.section);
    if (sec) sec.classList.add('active');
  });
});

const TRANSLATIONS = {
  en: {
    server_title:      'Server Configuration',
    server_desc:       'Connect the extension to your self-hosted relay server.',
    relay_url_label:   'Relay Server URL',
    relay_url_hint:    'Use your machine\'s local IP — not localhost.',
    btn_test:          'Test Connection',
    btn_save:          'Save',
    security_title:    'Security Settings',
    security_desc:     'Control how the vault locks and protects your data.',
    autolock_label:    'Auto-lock timeout',
    autolock_hint:     'Vault locks after this many minutes of inactivity.',
    minutes:           'min',
    appearance_title:  'Appearance',
    appearance_desc:   'Personalise the look of the extension.',
    theme_label:       'Theme',
    theme_dark:        'Dark',
    theme_light:       'Light',
    theme_system:      'System',
    language_title:    'Language',
    language_desc:     'Choose the language for the extension interface.',
    saved_ok:          'Settings saved.',
    connected_ok:      'Connected successfully.',
    connect_fail:      'Connection failed',
    enter_url:         'Enter a URL first.',
    invalid_url:       'Invalid URL format.',
    autolock_min:      'Must be at least 1 minute.',
    nav_server:        'Server',
    nav_security:      'Security',
    nav_appearance:    'Appearance',
    nav_language:      'Language',
    nav_accessibility: 'Accessibility',
    qr_expiry_label:   'QR Code expiry',
    qr_expiry_hint:    'How long the QR code stays valid before expiring. Default is 45 seconds.',
    nav_reset:         'Reset settings',
    reset_confirm:     'Type CONFIRM to reset all settings to defaults:',
    reset_cancelled:   'Reset cancelled — you must type CONFIRM exactly.',
    autolock_label_text: 'Auto-lock timeout',
    qr_expiry_label_text: 'QR Code expiry',
    accessibility_title: 'Accessibility',
    accessibility_desc:  'Adjust the interface to suit your needs. All settings save automatically.',
    text_size_label:     'Text size',
    text_size_hint:      'Adjusts text size across the entire extension.',
    anim_label:          'Animations',
    anim_desc:           'Enable transitions and motion effects',
    anim_hint:           'Turn off if you prefer reduced motion or find animations distracting.',
    custom_base_label:   'Base colour',
    custom_base_hint:    'Background & surfaces',
    custom_accent_label: 'Accent colour',
    custom_accent_hint:  'Buttons & highlights',
    custom_preview_text: 'Preview',
    custom_preview_btn:  'Button',
    custom_apply_btn:    'Apply Custom Theme',
    custom_card_label:   'Custom',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'Use your machine\'s local IP — not <code>localhost</code>.<br>Examples: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://my-server.com</code>',
    connect_testing:     'Testing…',
    http_error:          'Server responded with HTTP',
    connect_error:       'Could not connect:',
    not_fortispass:       'Connected, but this doesn\'t appear to be a fortispass relay server.',
    url_http_required:   'URL must start with http:// or https://',
  },
  es: {
    server_title:      'Configuración del servidor',
    server_desc:       'Conecta la extensión a tu servidor relay propio.',
    relay_url_label:   'URL del servidor relay',
    relay_url_hint:    'Usa la IP local de tu máquina, no localhost.',
    btn_test:          'Probar conexión',
    btn_save:          'Guardar',
    security_title:    'Configuración de seguridad',
    security_desc:     'Controla cómo se bloquea y protege el vault.',
    autolock_label:    'Tiempo de bloqueo automático',
    autolock_hint:     'El vault se bloquea tras estos minutos de inactividad.',
    minutes:           'min',
    appearance_title:  'Apariencia',
    appearance_desc:   'Personaliza el aspecto de la extensión.',
    theme_label:       'Tema',
    theme_dark:        'Oscuro',
    theme_light:       'Claro',
    theme_system:      'Sistema',
    language_title:    'Idioma',
    language_desc:     'Elige el idioma para la interfaz de la extensión.',
    saved_ok:          'Configuración guardada.',
    connected_ok:      'Conexión exitosa.',
    connect_fail:      'Error de conexión',
    enter_url:         'Introduce una URL primero.',
    invalid_url:       'Formato de URL no válido.',
    autolock_min:      'Debe ser al menos 1 minuto.',
    nav_server:        'Servidor',
    nav_security:      'Seguridad',
    nav_appearance:    'Apariencia',
    nav_language:      'Idioma',
    nav_accessibility: 'Accesibilidad',
    qr_expiry_label:   'Expiración del código QR',
    qr_expiry_hint:    'Tiempo que el código QR es válido antes de expirar. Por defecto 45 segundos.',
    nav_reset:         'Restablecer ajustes',
    reset_confirm:     'Escribe CONFIRM para restablecer todos los ajustes:',
    reset_cancelled:   'Restablecimiento cancelado — debes escribir CONFIRM exactamente.',
    autolock_label_text: 'Tiempo de bloqueo automático',
    qr_expiry_label_text: 'Expiración del código QR',
    accessibility_title: 'Accesibilidad',
    accessibility_desc:  'Ajusta la interfaz a tus necesidades. Todos los ajustes se guardan automáticamente.',
    text_size_label:     'Tamaño de texto',
    text_size_hint:      'Ajusta el tamaño del texto en toda la extensión.',
    anim_label:          'Animaciones',
    anim_desc:           'Activar transiciones y efectos de movimiento',
    anim_hint:           'Desactiva si prefieres movimiento reducido o las animaciones te distraen.',
    custom_base_label:   'Color base',
    custom_base_hint:    'Fondo y superficies',
    custom_accent_label: 'Color de acento',
    custom_accent_hint:  'Botones y resaltados',
    custom_preview_text: 'Vista previa',
    custom_preview_btn:  'Botón',
    custom_apply_btn:    'Aplicar tema personalizado',
    custom_card_label:   'Personalizado',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'Usa la IP local de tu máquina, no <code>localhost</code>.<br>Ejemplos: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://mi-servidor.com</code>',
    connect_testing:     'Probando…',
    http_error:          'El servidor respondió con HTTP',
    connect_error:       'No se pudo conectar:',
    not_fortispass:       'Conectado, pero esto no parece ser un servidor relay de fortispass.',
    url_http_required:   'La URL debe comenzar con http:// o https://',
  },
  de: {
    server_title:      'Server-Konfiguration',
    server_desc:       'Verbinde die Erweiterung mit deinem eigenen Relay-Server.',
    relay_url_label:   'Relay-Server-URL',
    relay_url_hint:    'Verwende die lokale IP deines Rechners, nicht localhost.',
    btn_test:          'Verbindung testen',
    btn_save:          'Speichern',
    security_title:    'Sicherheitseinstellungen',
    security_desc:     'Steuere, wie der Tresor gesperrt und geschützt wird.',
    autolock_label:    'Automatische Sperrzeit',
    autolock_hint:     'Der Tresor sperrt nach dieser Anzahl von Minuten Inaktivität.',
    minutes:           'Min',
    appearance_title:  'Erscheinungsbild',
    appearance_desc:   'Passe das Aussehen der Erweiterung an.',
    theme_label:       'Design',
    theme_dark:        'Dunkel',
    theme_light:       'Hell',
    theme_system:      'System',
    language_title:    'Sprache',
    language_desc:     'Wähle die Sprache für die Erweiterungsoberfläche.',
    saved_ok:          'Einstellungen gespeichert.',
    connected_ok:      'Erfolgreich verbunden.',
    connect_fail:      'Verbindung fehlgeschlagen',
    enter_url:         'Bitte zuerst eine URL eingeben.',
    invalid_url:       'Ungültiges URL-Format.',
    autolock_min:      'Mindestens 1 Minute erforderlich.',
    nav_server:        'Server',
    nav_security:      'Sicherheit',
    nav_appearance:    'Erscheinungsbild',
    nav_language:      'Sprache',
    nav_accessibility: 'Zugänglichkeit',
    qr_expiry_label:   'QR-Code-Ablauf',
    qr_expiry_hint:    'Wie lange der QR-Code gültig bleibt. Standard ist 45 Sekunden.',
    nav_reset:         'Einstellungen zurücksetzen',
    reset_confirm:     'Tippe CONFIRM, um alle Einstellungen zurückzusetzen:',
    reset_cancelled:   'Zurücksetzen abgebrochen — du musst genau CONFIRM eingeben.',
    autolock_label_text: 'Automatische Sperrzeit',
    qr_expiry_label_text: 'QR-Code-Ablauf',
    accessibility_title: 'Barrierefreiheit',
    accessibility_desc:  'Passe die Oberfläche an deine Bedürfnisse an. Alle Einstellungen werden automatisch gespeichert.',
    text_size_label:     'Textgröße',
    text_size_hint:      'Passt die Textgröße in der gesamten Erweiterung an.',
    anim_label:          'Animationen',
    anim_desc:           'Übergänge und Bewegungseffekte aktivieren',
    anim_hint:           'Deaktiviere, wenn du weniger Bewegung bevorzugst oder Animationen ablenken.',
    custom_base_label:   'Grundfarbe',
    custom_base_hint:    'Hintergrund & Oberflächen',
    custom_accent_label: 'Akzentfarbe',
    custom_accent_hint:  'Schaltflächen & Hervorhebungen',
    custom_preview_text: 'Vorschau',
    custom_preview_btn:  'Schaltfläche',
    custom_apply_btn:    'Benutzerdefiniertes Design anwenden',
    custom_card_label:   'Benutzerdefiniert',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'Verwende die lokale IP deines Rechners, nicht <code>localhost</code>.<br>Beispiele: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://mein-server.com</code>',
    connect_testing:     'Teste…',
    http_error:          'Server antwortete mit HTTP',
    connect_error:       'Verbindung fehlgeschlagen:',
    not_fortispass:       'Verbunden, aber dies scheint kein fortispass Relay-Server zu sein.',
    url_http_required:   'URL muss mit http:// oder https:// beginnen',
  },
  hr: {
    server_title:      'Konfiguracija poslužitelja',
    server_desc:       'Poveži proširenje s vlastitim relay poslužiteljem.',
    relay_url_label:   'URL relay poslužitelja',
    relay_url_hint:    'Koristi lokalnu IP adresu svog računala, ne localhost.',
    btn_test:          'Testiraj vezu',
    btn_save:          'Spremi',
    security_title:    'Sigurnosne postavke',
    security_desc:     'Kontroliraj kako se trezor zaključava i štiti.',
    autolock_label:    'Automatsko zaključavanje',
    autolock_hint:     'Trezor se zaključava nakon toliko minuta neaktivnosti.',
    minutes:           'min',
    appearance_title:  'Izgled',
    appearance_desc:   'Prilagodi izgled proširenja.',
    theme_label:       'Tema',
    theme_dark:        'Tamna',
    theme_light:       'Svijetla',
    theme_system:      'Sustav',
    language_title:    'Jezik',
    language_desc:     'Odaberi jezik sučelja proširenja.',
    saved_ok:          'Postavke spremljene.',
    connected_ok:      'Uspješno povezano.',
    connect_fail:      'Veza nije uspjela',
    enter_url:         'Prvo unesi URL.',
    invalid_url:       'Nevažeći format URL-a.',
    autolock_min:      'Mora biti barem 1 minuta.',
    nav_server:        'Poslužitelj',
    nav_security:      'Sigurnost',
    nav_appearance:    'Izgled',
    nav_language:      'Jezik',
    nav_accessibility: 'Pristupačnost',
    qr_expiry_label:   'Istek QR koda',
    qr_expiry_hint:    'Koliko dugo QR kod ostaje važeći. Zadano je 45 sekundi.',
    nav_reset:         'Resetiraj postavke',
    reset_confirm:     'Upiši CONFIRM za resetiranje svih postavki:',
    reset_cancelled:   'Resetiranje otkazano — moraš upisati točno CONFIRM.',
    autolock_label_text: 'Automatsko zaključavanje',
    qr_expiry_label_text: 'Istek QR koda',
    accessibility_title: 'Pristupačnost',
    accessibility_desc:  'Prilagodi sučelje svojim potrebama. Sve postavke se automatski spremaju.',
    text_size_label:     'Veličina teksta',
    text_size_hint:      'Prilagođava veličinu teksta u cijeloj ekstenziji.',
    anim_label:          'Animacije',
    anim_desc:           'Omogući prijelaze i efekte kretanja',
    anim_hint:           'Isključi ako preferiraš smanjeno kretanje ili te animacije ometaju.',
    custom_base_label:   'Osnovna boja',
    custom_base_hint:    'Pozadina i površine',
    custom_accent_label: 'Boja naglaska',
    custom_accent_hint:  'Gumbi i isticanja',
    custom_preview_text: 'Pregled',
    custom_preview_btn:  'Gumb',
    custom_apply_btn:    'Primijeni prilagođenu temu',
    custom_card_label:   'Prilagođeno',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'Koristi lokalnu IP adresu svog računala, ne <code>localhost</code>.<br>Primjeri: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://moj-server.com</code>',
    connect_testing:     'Testiranje…',
    http_error:          'Poslužitelj je odgovorio s HTTP',
    connect_error:       'Nije se moguće povezati:',
    not_fortispass:       'Spojeno, ali ovo ne izgleda kao fortispass relay poslužitelj.',
    url_http_required:   'URL mora počinjati s http:// ili https://',
  },
  it: {
    server_title:      'Configurazione server',
    server_desc:       'Connetti l\'estensione al tuo server relay.',
    relay_url_label:   'URL server relay',
    relay_url_hint:    'Usa l\'IP locale della tua macchina, non localhost.',
    btn_test:          'Testa connessione',
    btn_save:          'Salva',
    security_title:    'Impostazioni di sicurezza',
    security_desc:     'Controlla come il vault si blocca e si protegge.',
    autolock_label:    'Blocco automatico',
    autolock_hint:     'Il vault si blocca dopo questi minuti di inattività.',
    minutes:           'min',
    appearance_title:  'Aspetto',
    appearance_desc:   'Personalizza l\'aspetto dell\'estensione.',
    theme_label:       'Tema',
    theme_dark:        'Scuro',
    theme_light:       'Chiaro',
    theme_system:      'Sistema',
    language_title:    'Lingua',
    language_desc:     'Scegli la lingua per l\'interfaccia dell\'estensione.',
    saved_ok:          'Impostazioni salvate.',
    connected_ok:      'Connesso con successo.',
    connect_fail:      'Connessione fallita',
    enter_url:         'Inserisci prima un URL.',
    invalid_url:       'Formato URL non valido.',
    autolock_min:      'Deve essere almeno 1 minuto.',
    nav_server:        'Server',
    nav_security:      'Sicurezza',
    nav_appearance:    'Aspetto',
    nav_language:      'Lingua',
    nav_accessibility: 'Accessibilità',
    qr_expiry_label:   'Scadenza codice QR',
    qr_expiry_hint:    'Durata della validità del codice QR. Il valore predefinito è 45 secondi.',
    nav_reset:         'Reimposta impostazioni',
    reset_confirm:     'Scrivi CONFIRM per reimpostare tutte le impostazioni:',
    reset_cancelled:   'Ripristino annullato — devi scrivere esattamente CONFIRM.',
    autolock_label_text: 'Blocco automatico',
    qr_expiry_label_text: 'Scadenza codice QR',
    accessibility_title: 'Accessibilità',
    accessibility_desc:  'Personalizza l\'interfaccia alle tue esigenze. Tutte le impostazioni si salvano automaticamente.',
    text_size_label:     'Dimensione testo',
    text_size_hint:      'Regola la dimensione del testo nell\'intera estensione.',
    anim_label:          'Animazioni',
    anim_desc:           'Abilita transizioni ed effetti di movimento',
    anim_hint:           'Disattiva se preferisci movimenti ridotti o le animazioni ti distraggono.',
    custom_base_label:   'Colore base',
    custom_base_hint:    'Sfondo e superfici',
    custom_accent_label: 'Colore accento',
    custom_accent_hint:  'Pulsanti e evidenziazioni',
    custom_preview_text: 'Anteprima',
    custom_preview_btn:  'Pulsante',
    custom_apply_btn:    'Applica tema personalizzato',
    custom_card_label:   'Personalizzato',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'Usa l\'IP locale della tua macchina, non <code>localhost</code>.<br>Esempi: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://mio-server.com</code>',
    connect_testing:     'Connessione in corso…',
    http_error:          'Il server ha risposto con HTTP',
    connect_error:       'Impossibile connettersi:',
    not_fortispass:       'Connesso, ma questo non sembra un server relay fortispass.',
    url_http_required:   'L\'URL deve iniziare con http:// o https://',
  },
  ru: {
    server_title:      'Настройка сервера',
    server_desc:       'Подключите расширение к вашему собственному серверу-ретранслятору.',
    relay_url_label:   'URL сервера-ретранслятора',
    relay_url_hint:    'Используйте локальный IP-адрес компьютера, а не localhost.',
    btn_test:          'Проверить соединение',
    btn_save:          'Сохранить',
    security_title:    'Настройки безопасности',
    security_desc:     'Управляйте блокировкой и защитой хранилища.',
    autolock_label:    'Автоблокировка',
    autolock_hint:     'Хранилище блокируется после указанного числа минут бездействия.',
    minutes:           'мин',
    appearance_title:  'Внешний вид',
    appearance_desc:   'Настройте оформление расширения.',
    theme_label:       'Тема',
    theme_dark:        'Тёмная',
    theme_light:       'Светлая',
    theme_system:      'Системная',
    language_title:    'Язык',
    language_desc:     'Выберите язык интерфейса расширения.',
    saved_ok:          'Настройки сохранены.',
    connected_ok:      'Успешно подключено.',
    connect_fail:      'Ошибка подключения',
    enter_url:         'Сначала введите URL.',
    invalid_url:       'Неверный формат URL.',
    autolock_min:      'Должно быть не менее 1 минуты.',
    nav_server:        'Сервер',
    nav_security:      'Безопасность',
    nav_appearance:    'Внешний вид',
    nav_language:      'Язык',
    nav_accessibility: 'Доступность',
    qr_expiry_label:   'Срок действия QR-кода',
    qr_expiry_hint:    'Время действия QR-кода до истечения срока. По умолчанию 45 секунд.',
    nav_reset:         'Сбросить настройки',
    reset_confirm:     'Введите CONFIRM для сброса всех настроек:',
    reset_cancelled:   'Сброс отменён — необходимо ввести CONFIRM точно.',
    autolock_label_text: 'Автоблокировка',
    qr_expiry_label_text: 'Срок действия QR-кода',
    accessibility_title: 'Специальные возможности',
    accessibility_desc:  'Настройте интерфейс под свои нужды. Все настройки сохраняются автоматически.',
    text_size_label:     'Размер текста',
    text_size_hint:      'Изменяет размер текста во всём расширении.',
    anim_label:          'Анимации',
    anim_desc:           'Включить переходы и эффекты движения',
    anim_hint:           'Отключите, если предпочитаете меньше движений или анимации отвлекают.',
    custom_base_label:   'Основной цвет',
    custom_base_hint:    'Фон и поверхности',
    custom_accent_label: 'Акцентный цвет',
    custom_accent_hint:  'Кнопки и выделения',
    custom_preview_text: 'Превью',
    custom_preview_btn:  'Кнопка',
    custom_apply_btn:    'Применить пользовательскую тему',
    custom_card_label:   'Своя тема',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'Используйте локальный IP-адрес компьютера, а не <code>localhost</code>.<br>Примеры: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://мой-сервер.com</code>',
    connect_testing:     'Проверка…',
    http_error:          'Сервер ответил с HTTP',
    connect_error:       'Не удалось подключиться:',
    not_fortispass:       'Подключено, но это не похоже на relay-сервер fortispass.',
    url_http_required:   'URL должен начинаться с http:// или https://',
  },
  ja: {
    server_title:      'サーバー設定',
    server_desc:       '拡張機能をセルフホスト型リレーサーバーに接続します。',
    relay_url_label:   'リレーサーバーURL',
    relay_url_hint:    'localhostではなく、マシンのローカルIPを使用してください。',
    btn_test:          '接続テスト',
    btn_save:          '保存',
    security_title:    'セキュリティ設定',
    security_desc:     'ボルトのロック方法と保護を制御します。',
    autolock_label:    '自動ロックタイムアウト',
    autolock_hint:     '指定した分数の非アクティブ後にボルトをロックします。',
    minutes:           '分',
    appearance_title:  '外観',
    appearance_desc:   '拡張機能の外観をカスタマイズします。',
    theme_label:       'テーマ',
    theme_dark:        'ダーク',
    theme_light:       'ライト',
    theme_system:      'システム',
    language_title:    '言語',
    language_desc:     '拡張機能のインターフェース言語を選択します。',
    saved_ok:          '設定を保存しました。',
    connected_ok:      '接続に成功しました。',
    connect_fail:      '接続に失敗しました',
    enter_url:         '先にURLを入力してください。',
    invalid_url:       'URLの形式が無効です。',
    autolock_min:      '1分以上である必要があります。',
    nav_server:        'サーバー',
    nav_security:      'セキュリティ',
    nav_appearance:    '外観',
    nav_language:      '言語',
    nav_accessibility: 'アクセシビリティ',
    qr_expiry_label:   'QRコード有効期限',
    qr_expiry_hint:    'QRコードが有効な時間。デフォルトは45秒です。',
    nav_reset:         '設定をリセット',
    reset_confirm:     'すべての設定をリセットするにはCONFIRMと入力してください:',
    reset_cancelled:   'リセットをキャンセルしました — CONFIRMと正確に入力してください。',
    autolock_label_text: '自動ロックタイムアウト',
    qr_expiry_label_text: 'QRコード有効期限',
    accessibility_title: 'アクセシビリティ',
    accessibility_desc:  'インターフェースをニーズに合わせて調整します。すべての設定は自動的に保存されます。',
    text_size_label:     'テキストサイズ',
    text_size_hint:      '拡張機能全体のテキストサイズを調整します。',
    anim_label:          'アニメーション',
    anim_desc:           'トランジションとモーション効果を有効にする',
    anim_hint:           '動きを減らしたい場合やアニメーションが気になる場合はオフにしてください。',
    custom_base_label:   'ベースカラー',
    custom_base_hint:    '背景とサーフェス',
    custom_accent_label: 'アクセントカラー',
    custom_accent_hint:  'ボタンとハイライト',
    custom_preview_text: 'プレビュー',
    custom_preview_btn:  'ボタン',
    custom_apply_btn:    'カスタムテーマを適用',
    custom_card_label:   'カスタム',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'localhostではなく、マシンのローカルIPを使用してください。<br>例: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://my-server.com</code>',
    connect_testing:     '接続中…',
    http_error:          'サーバーがHTTPで応答しました',
    connect_error:       '接続できませんでした:',
    not_fortispass:       '接続しましたが、これはfortispass relayサーバーではないようです。',
    url_http_required:   'URLはhttp://またはhttps://で始まる必要があります',
  },
  fr: {
    server_title:      'Configuration du serveur',
    server_desc:       'Connectez l\'extension à votre serveur relais auto-hébergé.',
    relay_url_label:   'URL du serveur relais',
    relay_url_hint:    'Utilisez l\'IP locale de votre machine, pas localhost.',
    btn_test:          'Tester la connexion',
    btn_save:          'Enregistrer',
    security_title:    'Paramètres de sécurité',
    security_desc:     'Contrôlez comment le coffre se verrouille et se protège.',
    autolock_label:    'Verrouillage automatique',
    autolock_hint:     'Le coffre se verrouille après ces minutes d\'inactivité.',
    minutes:           'min',
    appearance_title:  'Apparence',
    appearance_desc:   'Personnalisez l\'aspect de l\'extension.',
    theme_label:       'Thème',
    theme_dark:        'Sombre',
    theme_light:       'Clair',
    theme_system:      'Système',
    language_title:    'Langue',
    language_desc:     'Choisissez la langue de l\'interface de l\'extension.',
    saved_ok:          'Paramètres enregistrés.',
    connected_ok:      'Connexion réussie.',
    connect_fail:      'Échec de la connexion',
    enter_url:         'Entrez d\'abord une URL.',
    invalid_url:       'Format d\'URL invalide.',
    autolock_min:      'Doit être d\'au moins 1 minute.',
    nav_server:        'Serveur',
    nav_security:      'Sécurité',
    nav_appearance:    'Apparence',
    nav_language:      'Langue',
    nav_accessibility: 'Accessibilité',
    qr_expiry_label:   'Expiration du QR code',
    qr_expiry_hint:    'Durée de validité du QR code avant expiration. Par défaut 45 secondes.',
    nav_reset:         'Réinitialiser les paramètres',
    reset_confirm:     'Tapez CONFIRM pour réinitialiser tous les paramètres :',
    reset_cancelled:   'Réinitialisation annulée — vous devez taper CONFIRM exactement.',
    autolock_label_text: 'Verrouillage automatique',
    qr_expiry_label_text: 'Expiration du QR code',
    accessibility_title: 'Accessibilité',
    accessibility_desc:  'Adaptez l\'interface à vos besoins. Tous les paramètres sont enregistrés automatiquement.',
    text_size_label:     'Taille du texte',
    text_size_hint:      'Ajuste la taille du texte dans toute l\'extension.',
    anim_label:          'Animations',
    anim_desc:           'Activer les transitions et effets de mouvement',
    anim_hint:           'Désactivez si vous préférez moins de mouvement ou si les animations vous distraient.',
    custom_base_label:   'Couleur de base',
    custom_base_hint:    'Arrière-plan et surfaces',
    custom_accent_label: 'Couleur d\'accent',
    custom_accent_hint:  'Boutons et surlignages',
    custom_preview_text: 'Aperçu',
    custom_preview_btn:  'Bouton',
    custom_apply_btn:    'Appliquer le thème personnalisé',
    custom_card_label:   'Personnalisé',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'Utilisez l\'IP locale de votre machine, pas <code>localhost</code>.<br>Exemples : <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://mon-serveur.com</code>',
    connect_testing:     'Test en cours…',
    http_error:          'Le serveur a répondu avec HTTP',
    connect_error:       'Impossible de se connecter :',
    not_fortispass:       'Connecté, mais ceci ne semble pas être un serveur relais fortispass.',
    url_http_required:   'L\'URL doit commencer par http:// ou https://',
  },
  ar: {
    server_title:      'إعداد الخادم',
    server_desc:       'اربط الامتداد بخادم الترحيل الخاص بك.',
    relay_url_label:   'عنوان URL لخادم الترحيل',
    relay_url_hint:    'استخدم عنوان IP المحلي للجهاز، وليس localhost.',
    btn_test:          'اختبار الاتصال',
    btn_save:          'حفظ',
    security_title:    'إعدادات الأمان',
    security_desc:     'تحكم في كيفية قفل الخزنة وحمايتها.',
    autolock_label:    'القفل التلقائي',
    autolock_hint:     'تُقفل الخزنة بعد هذا العدد من دقائق الخمول.',
    minutes:           'د',
    appearance_title:  'المظهر',
    appearance_desc:   'خصّص مظهر الامتداد.',
    theme_label:       'السمة',
    theme_dark:        'داكن',
    theme_light:       'فاتح',
    theme_system:      'النظام',
    language_title:    'اللغة',
    language_desc:     'اختر لغة واجهة الامتداد.',
    saved_ok:          'تم حفظ الإعدادات.',
    connected_ok:      'تم الاتصال بنجاح.',
    connect_fail:      'فشل الاتصال',
    enter_url:         'أدخل عنوان URL أولاً.',
    invalid_url:       'تنسيق URL غير صالح.',
    autolock_min:      'يجب أن يكون دقيقة واحدة على الأقل.',
    nav_server:        'الخادم',
    nav_security:      'الأمان',
    nav_appearance:    'المظهر',
    nav_language:      'اللغة',
    nav_accessibility: 'إمكانية الوصول',
    qr_expiry_label:   'انتهاء صلاحية QR',
    qr_expiry_hint:    'مدة صلاحية رمز QR قبل انتهائه. الافتراضي 45 ثانية.',
    nav_reset:         'إعادة ضبط الإعدادات',
    reset_confirm:     'اكتب CONFIRM لإعادة ضبط جميع الإعدادات:',
    reset_cancelled:   'تم إلغاء إعادة الضبط — يجب كتابة CONFIRM بالضبط.',
    autolock_label_text: 'القفل التلقائي',
    qr_expiry_label_text: 'انتهاء صلاحية QR',
    accessibility_title: 'إمكانية الوصول',
    accessibility_desc:  'اضبط الواجهة وفق احتياجاتك. تُحفظ جميع الإعدادات تلقائياً.',
    text_size_label:     'حجم النص',
    text_size_hint:      'يضبط حجم النص في جميع أنحاء الامتداد.',
    anim_label:          'الرسوم المتحركة',
    anim_desc:           'تفعيل التأثيرات الانتقالية والحركية',
    anim_hint:           'أوقف إذا كنت تفضل حركة أقل أو إذا كانت الرسوم تشتت انتباهك.',
    custom_base_label:   'اللون الأساسي',
    custom_base_hint:    'الخلفية والأسطح',
    custom_accent_label: 'لون التمييز',
    custom_accent_hint:  'الأزرار والإبرازات',
    custom_preview_text: 'معاينة',
    custom_preview_btn:  'زر',
    custom_apply_btn:    'تطبيق السمة المخصصة',
    custom_card_label:   'مخصص',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'استخدم عنوان IP المحلي للجهاز، وليس <code>localhost</code>.<br>أمثلة: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://my-server.com</code>',
    connect_testing:     'جارٍ الاختبار…',
    http_error:          'استجاب الخادم بـ HTTP',
    connect_error:       'تعذّر الاتصال:',
    not_fortispass:       'متصل، لكن هذا لا يبدو أنه خادم fortispass relay.',
    url_http_required:   'يجب أن يبدأ الرابط بـ http:// أو https://',
  },
  zh: {
    server_title:      '服务器配置',
    server_desc:       '将扩展连接到您的自托管中继服务器。',
    relay_url_label:   '中继服务器地址',
    relay_url_hint:    '请使用计算机的本地IP地址，而非localhost。',
    btn_test:          '测试连接',
    btn_save:          '保存',
    security_title:    '安全设置',
    security_desc:     '控制密码库的锁定和保护方式。',
    autolock_label:    '自动锁定时间',
    autolock_hint:     '密码库在此分钟数不活动后自动锁定。',
    minutes:           '分钟',
    appearance_title:  '外观',
    appearance_desc:   '个性化扩展的外观。',
    theme_label:       '主题',
    theme_dark:        '深色',
    theme_light:       '浅色',
    theme_system:      '跟随系统',
    language_title:    '语言',
    language_desc:     '选择扩展界面的语言。',
    saved_ok:          '设置已保存。',
    connected_ok:      '连接成功。',
    connect_fail:      '连接失败',
    enter_url:         '请先输入网址。',
    invalid_url:       '网址格式无效。',
    autolock_min:      '至少需要1分钟。',
    nav_server:        '服务器',
    nav_security:      '安全',
    nav_appearance:    '外观',
    nav_language:      '语言',
    nav_accessibility: '无障碍',
    qr_expiry_label:   '二维码有效期',
    qr_expiry_hint:    '二维码在过期前保持有效的时间。默认为45秒。',
    nav_reset:         '重置设置',
    reset_confirm:     '输入 CONFIRM 以重置所有设置：',
    reset_cancelled:   '已取消重置 — 必须准确输入 CONFIRM。',
    autolock_label_text: '自动锁定时间',
    qr_expiry_label_text: '二维码有效期',
    accessibility_title: '无障碍',
    accessibility_desc:  '根据您的需求调整界面。所有设置自动保存。',
    text_size_label:     '文字大小',
    text_size_hint:      '调整整个扩展的文字大小。',
    anim_label:          '动画',
    anim_desc:           '启用过渡和动效',
    anim_hint:           '如果您喜欢减少动效或动画令您分心，请关闭。',
    custom_base_label:   '基础颜色',
    custom_base_hint:    '背景和表面',
    custom_accent_label: '强调颜色',
    custom_accent_hint:  '按钮和高亮',
    custom_preview_text: '预览',
    custom_preview_btn:  '按钮',
    custom_apply_btn:    '应用自定义主题',
    custom_card_label:   '自定义',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: '请使用计算机的本地IP地址，而非 <code>localhost</code>。<br>示例：<code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://my-server.com</code>',
    connect_testing:     '测试中…',
    http_error:          '服务器响应 HTTP',
    connect_error:       '无法连接：',
    not_fortispass:       '已连接，但这似乎不是 fortispass relay 服务器。',
    url_http_required:   'URL 必须以 http:// 或 https:// 开头',
  },  hi: {
    server_title:      'सर्वर कॉन्फ़िगरेशन',
    server_desc:       'एक्सटेंशन को अपने स्व-होस्टेड रिले सर्वर से कनेक्ट करें।',
    relay_url_label:   'रिले सर्वर URL',
    relay_url_hint:    'अपने मशीन का स्थानीय IP उपयोग करें, localhost नहीं।',
    btn_test:          'कनेक्शन जांचें',
    btn_save:          'सहेजें',
    security_title:    'सुरक्षा सेटिंग',
    security_desc:     'वॉल्ट के लॉक होने और डेटा सुरक्षा को नियंत्रित करें।',
    autolock_label:    'ऑटो-लॉक टाइमआउट',
    autolock_hint:     'निष्क्रियता के इतने मिनट बाद वॉल्ट लॉक हो जाता है।',
    minutes:           'मिनट',
    qr_expiry_label:   'QR कोड समाप्ति',
    qr_expiry_hint:    'QR कोड समाप्त होने से पहले कितने समय तक वैध रहता है। डिफ़ॉल्ट 45 सेकंड है।',
    nav_reset:         'सेटिंग रीसेट करें',
    reset_confirm:     'सभी सेटिंग रीसेट करने के लिए CONFIRM टाइप करें:',
    reset_cancelled:   'रीसेट रद्द — आपको बिल्कुल CONFIRM टाइप करना होगा।',
    autolock_label_text: 'ऑटो-लॉक टाइमआउट',
    qr_expiry_label_text: 'QR कोड समाप्ति',
    accessibility_title: 'पहुंच',
    accessibility_desc:  'इंटरफ़ेस को अपनी ज़रूरतों के अनुसार समायोजित करें। सभी सेटिंग स्वचालित रूप से सहेजी जाती हैं।',
    text_size_label:     'पाठ आकार',
    text_size_hint:      'पूरे एक्सटेंशन में पाठ का आकार समायोजित करता है।',
    anim_label:          'एनिमेशन',
    anim_desc:           'संक्रमण और गति प्रभाव सक्षम करें',
    anim_hint:           'बंद करें यदि आप कम गति पसंद करते हैं या एनिमेशन विचलित करते हैं।',
    custom_base_label:   'आधार रंग',
    custom_base_hint:    'पृष्ठभूमि और सतहें',
    custom_accent_label: 'एक्सेंट रंग',
    custom_accent_hint:  'बटन और हाइलाइट',
    custom_preview_text: 'पूर्वावलोकन',
    custom_preview_btn:  'बटन',
    custom_apply_btn:    'कस्टम थीम लागू करें',
    custom_card_label:   'कस्टम',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: 'अपनी मशीन का स्थानीय IP उपयोग करें, <code>localhost</code> नहीं।<br>उदाहरण: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://my-server.com</code>',
    connect_testing:     'परीक्षण हो रहा है…',
    http_error:          'सर्वर ने HTTP के साथ जवाब दिया',
    connect_error:       'कनेक्ट नहीं हो सका:',
    not_fortispass:       'कनेक्ट हो गया, लेकिन यह fortispass relay सर्वर नहीं लगता।',
    url_http_required:   'URL http:// या https:// से शुरू होना चाहिए',
    appearance_title:  'रूप-रंग',
    appearance_desc:   'एक्सटेंशन का स्वरूप अनुकूलित करें।',
    theme_label:       'थीम',
    theme_dark:        'डार्क',
    theme_light:       'लाइट',
    theme_system:      'सिस्टम',
    language_title:    'भाषा',
    language_desc:     'एक्सटेंशन इंटरफ़ेस की भाषा चुनें।',
    saved_ok:          'सेटिंग सहेजी गई।',
    connected_ok:      'सफलतापूर्वक कनेक्ट हुआ।',
    connect_fail:      'कनेक्शन विफल',
    enter_url:         'पहले एक URL दर्ज करें।',
    invalid_url:       'अमान्य URL प्रारूप।',
    autolock_min:      'कम से कम 1 मिनट होना चाहिए।',
    nav_server:        'सर्वर',
    nav_security:      'सुरक्षा',
    nav_appearance:    'रूप-रंग',
    nav_language:      'भाषा',
    nav_accessibility: 'पहुंच',
  },
  ko: {
    server_title:      '서버 구성',
    server_desc:       '확장 프로그램을 자체 호스팅 릴레이 서버에 연결합니다.',
    relay_url_label:   '릴레이 서버 URL',
    relay_url_hint:    'localhost가 아닌 컴퓨터의 로컬 IP를 사용하세요.',
    btn_test:          '연결 테스트',
    btn_save:          '저장',
    security_title:    '보안 설정',
    security_desc:     '보관함 잠금 및 데이터 보호 방법을 제어합니다.',
    autolock_label:    '자동 잠금 시간',
    autolock_hint:     '지정한 분 동안 비활성 상태이면 보관함이 잠깁니다.',
    minutes:           '분',
    qr_expiry_label:   'QR 코드 만료',
    qr_expiry_hint:    'QR 코드가 만료되기 전 유효한 시간. 기본값은 45초입니다.',
    nav_reset:         '설정 초기화',
    reset_confirm:     '모든 설정을 초기화하려면 CONFIRM을 입력하세요:',
    reset_cancelled:   '초기화가 취소되었습니다 — CONFIRM을 정확히 입력해야 합니다.',
    autolock_label_text: '자동 잠금 시간',
    qr_expiry_label_text: 'QR 코드 만료',
    accessibility_title: '접근성',
    accessibility_desc:  '인터페이스를 필요에 맞게 조정하세요. 모든 설정은 자동으로 저장됩니다.',
    text_size_label:     '텍스트 크기',
    text_size_hint:      '확장 프로그램 전체의 텍스트 크기를 조정합니다.',
    anim_label:          '애니메이션',
    anim_desc:           '전환 및 모션 효과 활성화',
    anim_hint:           '움직임을 줄이거나 애니메이션이 방해되면 꺼주세요.',
    custom_base_label:   '기본 색상',
    custom_base_hint:    '배경 및 표면',
    custom_accent_label: '강조 색상',
    custom_accent_hint:  '버튼 및 강조 표시',
    custom_preview_text: '미리보기',
    custom_preview_btn:  '버튼',
    custom_apply_btn:    '커스텀 테마 적용',
    custom_card_label:   '커스텀',
    relay_placeholder:   'http://192.168.1.x:8080',
    relay_url_hint_html: '로컬호스트 대신 컴퓨터의 로컬 IP를 사용하세요 (<code>localhost</code> 아님).<br>예시: <code>http://192.168.1.105:8080</code> &nbsp;·&nbsp; <code>https://my-server.com</code>',
    connect_testing:     '테스트 중…',
    http_error:          '서버가 HTTP로 응답했습니다',
    connect_error:       '연결할 수 없습니다:',
    not_fortispass:       '연결됨, 그러나 fortispass relay 서버가 아닌 것 같습니다.',
    url_http_required:   'URL은 http:// 또는 https://로 시작해야 합니다',
    appearance_title:  '외관',
    appearance_desc:   '확장 프로그램의 모양을 맞춤 설정합니다.',
    theme_label:       '테마',
    theme_dark:        '어두운',
    theme_light:       '밝은',
    theme_system:      '시스템',
    language_title:    '언어',
    language_desc:     '확장 프로그램 인터페이스 언어를 선택합니다.',
    saved_ok:          '설정이 저장되었습니다.',
    connected_ok:      '연결에 성공했습니다.',
    connect_fail:      '연결 실패',
    enter_url:         '먼저 URL을 입력하세요.',
    invalid_url:       '잘못된 URL 형식입니다.',
    autolock_min:      '최소 1분이어야 합니다.',
    nav_server:        '서버',
    nav_security:      '보안',
    nav_appearance:    '외관',
    nav_language:      '언어',
    nav_accessibility: '접근성',
  },

};

const RTL_LANGS = new Set(['ar', 'he', 'fa', 'ur']);

function t(key, lang) {
  lang = lang || 'en';
  return (TRANSLATIONS[lang] || TRANSLATIONS.en)[key] || TRANSLATIONS.en[key] || key;
}

function applyTranslations(lang) {
  const dir = RTL_LANGS.has(lang) ? 'rtl' : 'ltr';
  document.documentElement.dir  = dir;
  document.documentElement.lang = lang;

  // Standard: update first text node only, never wipes child elements
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const text = t(el.getAttribute('data-i18n'), lang);
    if (!text) return;
    const tn = Array.from(el.childNodes).find(n => n.nodeType === 3);
    if (tn) { tn.nodeValue = text; }
    else if (!el.children.length) { el.textContent = text; }
  });

  // HTML: hints that contain <code> tags etc
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const html = t(el.getAttribute('data-i18n-html'), lang);
    if (html) el.innerHTML = html;
  });

  // Label text node: labels containing child spans (live-value badges)
  document.querySelectorAll('[data-i18n-label]').forEach(el => {
    const text = t(el.getAttribute('data-i18n-label'), lang);
    if (!text) return;
    const tn = Array.from(el.childNodes).find(n => n.nodeType === 3);
    if (tn) tn.nodeValue = text + '\n              ';
  });

  // Placeholder
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const text = t(el.getAttribute('data-i18n-placeholder'), lang);
    if (text) el.placeholder = text;
  });

  // Nav item labels
  const navMap = {
    server: 'nav_server', security: 'nav_security',
    appearance: 'nav_appearance', language: 'nav_language',
    accessibility: 'nav_accessibility',
  };
  document.querySelectorAll('.nav-item[data-section]').forEach(el => {
    const span = el.querySelector('span');
    const key  = navMap[el.dataset.section];
    if (key && span) span.textContent = t(key, lang);
  });

  // Reset button label
  const resetSpan = document.querySelector('#btn-reset-settings span');
  if (resetSpan) resetSpan.textContent = t('nav_reset', lang);
}

// ─────────────────────────────────────────────────────────────────────────────
// FONT SIZE — apply directly to body so em units on all children inherit it
// ─────────────────────────────────────────────────────────────────────────────
function applyFontSize(px) {
  // Update the CSS variable — body uses var(--font-size), all em children inherit
  document.documentElement.style.setProperty('--font-size', px + 'px');
}

// ─────────────────────────────────────────────────────────────────────────────
// ANIMATIONS — toggle no-anim class; also zero inline transition on html+body
// because those elements have their own transition shorthand declarations
// ─────────────────────────────────────────────────────────────────────────────
function setAnimations(on) {
  document.documentElement.classList.toggle('no-anim', !on);
}

// ─────────────────────────────────────────────────────────────────────────────
// COLOUR HELPERS (for custom theme)
// ─────────────────────────────────────────────────────────────────────────────
function hexToHsl(hex) {
  let r = parseInt(hex.slice(1,3),16)/255;
  let g = parseInt(hex.slice(3,5),16)/255;
  let b = parseInt(hex.slice(5,7),16)/255;
  const max = Math.max(r,g,b), min = Math.min(r,g,b);
  let h, s, l = (max+min)/2;
  if (max === min) { h = s = 0; }
  else {
    const d = max-min;
    s = l > 0.5 ? d/(2-max-min) : d/(max+min);
    switch(max) {
      case r: h = ((g-b)/d + (g<b?6:0))/6; break;
      case g: h = ((b-r)/d + 2)/6;          break;
      default:h = ((r-g)/d + 4)/6;          break;
    }
  }
  return [h, s, l];
}
function hslToHex(h, s, l) {
  const q = l < 0.5 ? l*(1+s) : l+s-l*s, p = 2*l-q;
  const hue2rgb = (p,q,t) => {
    if(t<0)t+=1; if(t>1)t-=1;
    if(t<1/6) return p+(q-p)*6*t;
    if(t<1/2) return q;
    if(t<2/3) return p+(q-p)*(2/3-t)*6;
    return p;
  };
  if (s === 0) return '#' + [l,l,l].map(x => Math.round(x*255).toString(16).padStart(2,'0')).join('');
  return '#' + [hue2rgb(p,q,h+1/3), hue2rgb(p,q,h), hue2rgb(p,q,h-1/3)]
    .map(x => Math.round(x*255).toString(16).padStart(2,'0')).join('');
}
function shiftL(hex, delta) {
  const [h,s,l] = hexToHsl(hex);
  return hslToHex(h, s, Math.max(0, Math.min(1, l+delta)));
}

// ─────────────────────────────────────────────────────────────────────────────
// THEME
// ─────────────────────────────────────────────────────────────────────────────
function resolveTheme(th) {
  return th === 'system'
    ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
    : th;
}

function applyCustomVars(base, accent) {
  const r = document.documentElement;
  r.style.setProperty('--bg',         base);
  r.style.setProperty('--bg2',        shiftL(base,  0.04));
  r.style.setProperty('--bg3',        shiftL(base,  0.08));
  r.style.setProperty('--bg4',        shiftL(base,  0.12));
  r.style.setProperty('--border',     shiftL(base,  0.16));
  r.style.setProperty('--border2',    shiftL(base,  0.22));
  r.style.setProperty('--accent',     accent);
  r.style.setProperty('--accent-h',   shiftL(accent,  0.08));
  r.style.setProperty('--accent-a',   shiftL(accent, -0.08));
  r.style.setProperty('--nav-active', shiftL(base,  0.10));
  // Luminance-aware text: shift toward opposite end of lightness scale
  const rv = parseInt(base.slice(1,3),16)/255;
  const gv = parseInt(base.slice(3,5),16)/255;
  const bv = parseInt(base.slice(5,7),16)/255;
  const lum = 0.2126*rv + 0.7152*gv + 0.0722*bv;
  const isLight = lum > 0.4;
  r.style.setProperty('--text',       shiftL(base, isLight ? -0.75 : 0.88));
  r.style.setProperty('--text2',      shiftL(base, isLight ? -0.40 : 0.55));
  r.style.setProperty('--text3',      shiftL(base, isLight ? -0.20 : 0.32));
  r.style.setProperty('--fp-pass-color', isLight ? '#111111' : '#ffffff');
  updateCustomSwatch(base, accent);
}

function clearCustomVars() {
  ['--bg','--bg2','--bg3','--bg4','--border','--border2','--text','--text2',
   '--text3','--accent','--accent-h','--accent-a','--nav-active','--fp-pass-color']
    .forEach(p => document.documentElement.style.removeProperty(p));
}

function updateCustomSwatch(base, accent) {
  const r = document.documentElement;
  r.style.setProperty('--swatch-base',   base);
  r.style.setProperty('--swatch-accent', accent);
}

let themeTimer = null;
let currentTheme = 'dark';

function applyTheme(th, save) {
  currentTheme = th;
  clearTimeout(themeTimer);
  themeTimer = setTimeout(() => {
    if (th === 'custom') {
      document.documentElement.setAttribute('data-theme', 'custom');
    } else {
      clearCustomVars();
      document.documentElement.setAttribute('data-theme', resolveTheme(th));
    }
    document.querySelectorAll('.theme-opt').forEach(b =>
      b.classList.toggle('selected', b.dataset.theme === th)
    );
    if (save) chrome.storage.local.set({ theme: th });
  }, 40);
}

window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
  if (currentTheme === 'system') applyTheme('system', false);
});

// ─────────────────────────────────────────────────────────────────────────────
// LOAD STORED SETTINGS, THEN WIRE UP EVERYTHING
// ─────────────────────────────────────────────────────────────────────────────
chrome.storage.local.get([
  'relayURL', 'autoLockMinutes', 'theme', 'language',
  'qrExpirySecs', 'fontSize', 'animationsEnabled', 'customTheme'
], (stored) => {
  const lang          = stored.language          || 'en';
  const savedTheme    = stored.theme             || 'dark';
  const savedFontSize = parseInt(stored.fontSize) || 15;
  const animsOn       = stored.animationsEnabled !== false;
  const savedExpiry   = Math.min(50, Math.max(20, parseInt(stored.qrExpirySecs)    || 45));
  const savedAutoLock = Math.min(60, Math.max(1,  parseInt(stored.autoLockMinutes) || 15));
  const customTheme   = stored.customTheme || { base: '#0f0f1a', accent: '#5b5bd6' };

  // Apply animations preference first
  setAnimations(animsOn);

  // Apply font size
  applyFontSize(savedFontSize);

  // Apply theme
  if (savedTheme === 'custom') {
    applyCustomVars(customTheme.base, customTheme.accent);
  }
  applyTheme(savedTheme, false);

  // Apply language
  applyTranslations(lang);

  // ── Theme picker ────────────────────────────────────────────────────────────
  document.querySelectorAll('.theme-opt').forEach(btn => {
    btn.addEventListener('click', () => {
      const th = btn.dataset.theme;
      if (th === 'custom') {
        toggleBuilder(true);
      } else {
        toggleBuilder(false);
        applyTheme(th, true);
      }
    });
  });

  // ── Custom theme builder ────────────────────────────────────────────────────
  const builder     = document.getElementById('custom-theme-builder');
  const baseInput   = document.getElementById('custom-base');
  const accentInput = document.getElementById('custom-accent');
  const previewBar  = document.getElementById('custom-preview-bar');

  baseInput.value   = customTheme.base;
  accentInput.value = customTheme.accent;
  updateCustomSwatch(customTheme.base, customTheme.accent);

  function updateBuilderPreview() {
    const base = baseInput.value, accent = accentInput.value;
    const r = document.documentElement;
    r.style.setProperty('--preview-bg',     base);
    r.style.setProperty('--preview-border', shiftL(base, 0.16));
    r.style.setProperty('--preview-text',   shiftL(base, 0.88));
    r.style.setProperty('--preview-badge',  accent);
    updateCustomSwatch(base, accent);
  }
  updateBuilderPreview();
  baseInput.addEventListener('input',   updateBuilderPreview);
  accentInput.addEventListener('input', updateBuilderPreview);

  function toggleBuilder(show) {
    builder.classList.toggle('visible', show);
    if (show) {
      document.querySelectorAll('.theme-opt').forEach(b =>
        b.classList.toggle('selected', b.dataset.theme === 'custom')
      );
    }
  }

  document.getElementById('btn-apply-custom').addEventListener('click', () => {
    customTheme.base   = baseInput.value;
    customTheme.accent = accentInput.value;
    applyCustomVars(customTheme.base, customTheme.accent);
    document.documentElement.setAttribute('data-theme', 'custom');
    currentTheme = 'custom';
    chrome.storage.local.set({ theme: 'custom', customTheme });
    document.querySelectorAll('.theme-opt').forEach(b =>
      b.classList.toggle('selected', b.dataset.theme === 'custom')
    );
  });

  // Show builder if custom theme is already active
  if (savedTheme === 'custom') toggleBuilder(true);

  // ── Language picker ─────────────────────────────────────────────────────────
  document.querySelectorAll('.lang-opt').forEach(b =>
    b.classList.toggle('selected', b.dataset.lang === lang)
  );
  document.querySelectorAll('.lang-opt').forEach(btn =>
    btn.addEventListener('click', () => {
      const l = btn.dataset.lang;
      document.querySelectorAll('.lang-opt').forEach(b =>
        b.classList.toggle('selected', b.dataset.lang === l)
      );
      applyTranslations(l);
      chrome.storage.local.set({ language: l });
    })
  );

  // ── Auto-lock slider ────────────────────────────────────────────────────────
  const autoLockSlider = document.getElementById('auto-lock');
  const autoLockNum    = document.getElementById('auto-lock-num');

  function setAutoLock(v) {
    v = Math.min(60, Math.max(1, isNaN(v) ? 15 : v));
    autoLockSlider.value = v;
    autoLockNum.value    = v;
    chrome.storage.local.set({ autoLockMinutes: v });
  }
  setAutoLock(savedAutoLock);
  autoLockSlider.addEventListener('input',  () => setAutoLock(parseInt(autoLockSlider.value)));
  autoLockNum.addEventListener('input',     () => setAutoLock(parseInt(autoLockNum.value)));
  autoLockNum.addEventListener('blur',      () => setAutoLock(parseInt(autoLockNum.value)));

  // ── QR expiry slider ────────────────────────────────────────────────────────
  const qrSlider = document.getElementById('qr-expiry-slider');
  const qrNum    = document.getElementById('qr-expiry-num');

  function setQrExpiry(v) {
    v = Math.min(50, Math.max(20, isNaN(v) ? 45 : v));
    qrSlider.value = v;
    qrNum.value    = v;
    chrome.storage.local.set({ qrExpirySecs: v });
  }
  setQrExpiry(savedExpiry);
  qrSlider.addEventListener('input', () => setQrExpiry(parseInt(qrSlider.value)));
  qrNum.addEventListener('input',    () => setQrExpiry(parseInt(qrNum.value)));
  qrNum.addEventListener('blur',     () => setQrExpiry(parseInt(qrNum.value)));


  // ── Font size slider ────────────────────────────────────────────────────────
  const fontSlider = document.getElementById('font-size-slider');
  const fontNum    = document.getElementById('font-size-num');

  function setFontSize(v) {
    v = Math.min(20, Math.max(12, isNaN(v) ? 15 : v));
    fontSlider.value = v;
    fontNum.value    = v;
    applyFontSize(v);
    chrome.storage.local.set({ fontSize: v });
  }
  setFontSize(savedFontSize);
  fontSlider.addEventListener('input', () => setFontSize(parseInt(fontSlider.value)));
  fontNum.addEventListener('input',    () => setFontSize(parseInt(fontNum.value)));
  fontNum.addEventListener('blur',     () => setFontSize(parseInt(fontNum.value)));

  // ── Animation toggle ────────────────────────────────────────────────────────
  const animToggle = document.getElementById('anim-toggle');

  function setToggleVisual(on) {
    animToggle.dataset.on = on ? 'true' : 'false';
    animToggle.setAttribute('aria-checked', String(on));
  }
  setToggleVisual(animsOn);

  animToggle.addEventListener('click', () => {
    const nowOn = animToggle.dataset.on !== 'true';
    setToggleVisual(nowOn);
    setAnimations(nowOn);
    chrome.storage.local.set({ animationsEnabled: nowOn });
  });

  // ── Relay URL ───────────────────────────────────────────────────────────────
  if (stored.relayURL) document.getElementById('relay-url').value = stored.relayURL;

  // ── Save server ─────────────────────────────────────────────────────────────
  document.getElementById('btn-save-server').addEventListener('click', async () => {
    const url = document.getElementById('relay-url').value.trim().replace(/\/$/, '');
    const st  = document.getElementById('save-status-server');
    const lang = document.documentElement.lang || 'en';
    if (!url) { showMsg(st, 'err', t('enter_url', lang)); return; }
    try { new URL(url); } catch { showMsg(st, 'err', t('invalid_url', lang)); return; }
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      showMsg(st, 'err', t('url_http_required', lang)); return;
    }
    await chrome.storage.local.set({ relayURL: url });
    showMsg(st, 'ok', t('saved_ok', lang));
  });

  // ── Test connection ─────────────────────────────────────────────────────────
  document.getElementById('btn-test').addEventListener('click', async () => {
    const url = document.getElementById('relay-url').value.trim().replace(/\/$/, '');
    const st  = document.getElementById('test-status');
    const lang = document.documentElement.lang || 'en';
    if (!url) { showMsg(st, 'err', t('enter_url', lang)); return; }
    const btn = document.getElementById('btn-test');
    btn.disabled = true;
    showMsg(st, 'ok', t('connect_testing', lang));
    try {
      const resp = await fetch(url + '/health', { signal: AbortSignal.timeout(8000) });
      if (!resp.ok) {
        showMsg(st, 'err', t('http_error', lang) + ' ' + resp.status);
      } else if (resp.headers.get('X-Biokey') !== 'relay') {
        showMsg(st, 'warn', t('not_fortispass', lang));
      } else {
        showMsg(st, 'ok', t('connected_ok', lang));
      }
    } catch(e) {
      showMsg(st, 'err', t('connect_error', lang) + ' ' + e.message);
    } finally {
      btn.disabled = false;
    }
  });

  // ── Reset settings ──────────────────────────────────────────────────────────
  document.getElementById('btn-reset-settings').addEventListener('click', () => {
    const currentLang = document.documentElement.lang || 'en';
    const input = prompt(t('reset_confirm', currentLang));
    if (input !== 'CONFIRM') {
      if (input !== null) alert(t('reset_cancelled', currentLang));
      return;
    }
    chrome.storage.local.clear(() => {
      window.location.reload();
    });
  });

});

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────
function showMsg(el, type, msg) {
  if (el._hideTimer) { clearTimeout(el._hideTimer); el._hideTimer = null; }
  el.className     = 'status-msg';
  el.style.cssText = '';
  void el.offsetWidth;
  el.textContent   = msg;
  el.className     = 'status-msg ' + type;
  const delay = type === 'err' ? 3500 : 2500;
  el._hideTimer = setTimeout(() => {
    el.classList.add('hiding');
    setTimeout(() => {
      el.className     = 'status-msg';
      el.style.cssText = '';
      el._hideTimer    = null;
    }, 280);
  }, delay);
}
