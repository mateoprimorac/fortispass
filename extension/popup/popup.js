'use strict';

// ── i18n — inline translations for popup (can't import ES modules in classic script) ──
const POPUP_STRINGS = {
  en: {
    status_setup:     'Setup Required',
    setup_hint:       'Enter your relay server URL to get started.',
    btn_open_settings:'Open Settings',
    status_locked:    'Vault Locked',
    locked_hint:      'Open the fortispass app on your phone and scan the QR code to unlock.',
    btn_show_qr:      'Show QR Code',
    expires_in:       'Expires in',
    qr_hint:          'Scan with the Android app → biometric → done.',
    btn_cancel:       'Cancel',
    status_unlocked:  'Vault Unlocked',
    btn_retry:        'Try Again',
    autolock_in:      'Auto-locks in ~',
    autolock_min_unit:' min',
    autolock_close:   'Locks when browser closes',
    status_biometric: 'Waiting for Biometric',
    biometric_hint: 'Waiting for biometric confirmation on your phone…',
    tab_passwords:  'Passwords',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ Add password',
    btn_add_totp:  '＋ Add TOTP',
    form_add_password:  'Add password',
    form_edit_password:  'Edit password',
    form_add_totp:  'Add TOTP',
    form_edit_totp:  'Edit TOTP',
    cf_name_ph:  'Name (e.g. GitHub)',
    cf_url_ph:  'URL (e.g. https://github.com)',
    cf_username_ph:  'Username / email',
    cf_password_ph:  'Password',
    tf_name_ph:  'Name (e.g. GitHub)',
    tf_secret_ph:  'Secret key (Base32)',
    btn_save:  'Save',
    copy_password_title:  'Click to copy password',
    copy_code_title:  'Click to copy code',
    digits_6:  '6 digits',
    digits_8:  '8 digits',
    period_30:  '30 sec',
    period_60:  '60 sec',
    delete_confirm:  'Delete this entry?',
    nothing_here:  'Nothing here yet',
    gen_title:  'Password generator',
    gen_copy_title:  'Copy password',
    gen_length:  'Length',
    gen_generate:  'Generate',
  },
  es: {
    status_setup:     'Configuración requerida',
    setup_hint:       'Introduce la URL del servidor relay para empezar.',
    btn_open_settings:'Abrir ajustes',
    status_locked:    'Vault bloqueado',
    locked_hint:      'Abre la app fortispass en tu móvil y escanea el código QR para desbloquear.',
    btn_show_qr:      'Mostrar código QR',
    expires_in:       'Expira en',
    qr_hint:          'Escanea con la app Android → biométrico → listo.',
    btn_cancel:       'Cancelar',
    status_unlocked:  'Vault desbloqueado',
    btn_retry:        'Reintentar',
    autolock_in:      'Se bloquea en ~',
    autolock_min_unit:' min',
    autolock_close:   'Se bloquea al cerrar el navegador',
    status_biometric: 'Esperando biométrico',
    biometric_hint: 'Esperando confirmación biométrica en tu teléfono…',
    tab_passwords:  'Contraseñas',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ Añadir contraseña',
    btn_add_totp:  '＋ Añadir TOTP',
    form_add_password:  'Añadir contraseña',
    form_edit_password:  'Editar contraseña',
    form_add_totp:  'Añadir TOTP',
    form_edit_totp:  'Editar TOTP',
    cf_name_ph:  'Nombre (p.ej. GitHub)',
    cf_url_ph:  'URL (p.ej. https://github.com)',
    cf_username_ph:  'Usuario / correo',
    cf_password_ph:  'Contraseña',
    tf_name_ph:  'Nombre (p.ej. GitHub)',
    tf_secret_ph:  'Clave secreta (Base32)',
    btn_save:  'Guardar',
    copy_password_title:  'Clic para copiar contraseña',
    copy_code_title:  'Clic para copiar código',
    digits_6:  '6 dígitos',
    digits_8:  '8 dígitos',
    period_30:  '30 seg',
    period_60:  '60 seg',
    delete_confirm:  '¿Eliminar esta entrada?',
    nothing_here:  'Nada aquí todavía',
    gen_title:  'Generador de contraseñas',
    gen_copy_title:  'Copiar contraseña',
    gen_length:  'Longitud',
    gen_generate:  'Generar',
  },
  de: {
    status_setup:     'Einrichtung erforderlich',
    setup_hint:       'Gib die Relay-Server-URL ein, um zu beginnen.',
    btn_open_settings:'Einstellungen öffnen',
    status_locked:    'Tresor gesperrt',
    locked_hint:      'Öffne die fortispass-App auf deinem Handy und scanne den QR-Code.',
    btn_show_qr:      'QR-Code anzeigen',
    expires_in:       'Läuft ab in',
    qr_hint:          'Mit Android-App scannen → Biometrie → fertig.',
    btn_cancel:       'Abbrechen',
    status_unlocked:  'Tresor entsperrt',
    btn_retry:        'Erneut versuchen',
    autolock_in:      'Sperrt in ~',
    autolock_min_unit:' Min',
    autolock_close:   'Sperrt beim Schließen des Browsers',
    status_biometric: 'Warte auf Biometrie',
    biometric_hint: 'Warte auf biometrische Bestätigung auf deinem Handy…',
    tab_passwords:  'Passwörter',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ Passwort hinzufügen',
    btn_add_totp:  '＋ TOTP hinzufügen',
    form_add_password:  'Passwort hinzufügen',
    form_edit_password:  'Passwort bearbeiten',
    form_add_totp:  'TOTP hinzufügen',
    form_edit_totp:  'TOTP bearbeiten',
    cf_name_ph:  'Name (z.B. GitHub)',
    cf_url_ph:  'URL (z.B. https://github.com)',
    cf_username_ph:  'Benutzername / E-Mail',
    cf_password_ph:  'Passwort',
    tf_name_ph:  'Name (z.B. GitHub)',
    tf_secret_ph:  'Geheimschlüssel (Base32)',
    btn_save:  'Speichern',
    copy_password_title:  'Klicken zum Kopieren des Passworts',
    copy_code_title:  'Klicken zum Kopieren des Codes',
    digits_6:  '6 Stellen',
    digits_8:  '8 Stellen',
    period_30:  '30 Sek',
    period_60:  '60 Sek',
    delete_confirm:  'Diesen Eintrag löschen?',
    nothing_here:  'Noch nichts hier',
    gen_title:  'Passwortgenerator',
    gen_copy_title:  'Passwort kopieren',
    gen_length:  'Länge',
    gen_generate:  'Generieren',
  },
  hr: {
    status_setup:     'Potrebna postavka',
    setup_hint:       'Unesi URL relay poslužitelja za početak.',
    btn_open_settings:'Otvori postavke',
    status_locked:    'Trezor zaključan',
    locked_hint:      'Otvori fortispass aplikaciju na mobitelu i skeniraj QR kod.',
    btn_show_qr:      'Prikaži QR kod',
    expires_in:       'Istječe za',
    qr_hint:          'Skeniraj Android aplikacijom → biometrija → gotovo.',
    btn_cancel:       'Odustani',
    status_unlocked:  'Trezor otključan',
    btn_retry:        'Pokušaj ponovo',
    autolock_in:      'Zaključava za ~',
    autolock_min_unit:' min',
    autolock_close:   'Zaključava zatvaranjem preglednika',
    status_biometric: 'Čekanje biometrije',
    biometric_hint: 'Čekanje biometrijske potvrde na vašem telefonu…',
    tab_passwords:  'Lozinke',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ Dodaj lozinku',
    btn_add_totp:  '＋ Dodaj TOTP',
    form_add_password:  'Dodaj lozinku',
    form_edit_password:  'Uredi lozinku',
    form_add_totp:  'Dodaj TOTP',
    form_edit_totp:  'Uredi TOTP',
    cf_name_ph:  'Naziv (npr. GitHub)',
    cf_url_ph:  'URL (npr. https://github.com)',
    cf_username_ph:  'Korisničko ime / e-mail',
    cf_password_ph:  'Lozinka',
    tf_name_ph:  'Naziv (npr. GitHub)',
    tf_secret_ph:  'Tajni ključ (Base32)',
    btn_save:  'Spremi',
    copy_password_title:  'Klikni za kopiranje lozinke',
    copy_code_title:  'Klikni za kopiranje koda',
    digits_6:  '6 znamenki',
    digits_8:  '8 znamenki',
    period_30:  '30 sek',
    period_60:  '60 sek',
    delete_confirm:  'Izbrisati ovaj unos?',
    nothing_here:  'Još ništa ovdje',
    gen_title:  'Generator lozinki',
    gen_copy_title:  'Kopiraj lozinku',
    gen_length:  'Duljina',
    gen_generate:  'Generiraj',
  },
  it: {
    status_setup:     'Configurazione richiesta',
    setup_hint:       'Inserisci l\'URL del server relay per iniziare.',
    btn_open_settings:'Apri impostazioni',
    status_locked:    'Vault bloccato',
    locked_hint:      'Apri l\'app fortispass sul telefono e scansiona il codice QR.',
    btn_show_qr:      'Mostra codice QR',
    expires_in:       'Scade tra',
    qr_hint:          'Scansiona con l\'app Android → biometria → fatto.',
    btn_cancel:       'Annulla',
    status_unlocked:  'Vault sbloccato',
    btn_retry:        'Riprova',
    autolock_in:      'Si blocca tra ~',
    autolock_min_unit:' min',
    autolock_close:   'Si blocca alla chiusura del browser',
    status_biometric: 'In attesa biometria',
    biometric_hint: 'In attesa di conferma biometrica sul tuo telefono…',
    tab_passwords:  'Password',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ Aggiungi password',
    btn_add_totp:  '＋ Aggiungi TOTP',
    form_add_password:  'Aggiungi password',
    form_edit_password:  'Modifica password',
    form_add_totp:  'Aggiungi TOTP',
    form_edit_totp:  'Modifica TOTP',
    cf_name_ph:  'Nome (es. GitHub)',
    cf_url_ph:  'URL (es. https://github.com)',
    cf_username_ph:  'Utente / email',
    cf_password_ph:  'Password',
    tf_name_ph:  'Nome (es. GitHub)',
    tf_secret_ph:  'Chiave segreta (Base32)',
    btn_save:  'Salva',
    copy_password_title:  'Clic per copiare la password',
    copy_code_title:  'Clic per copiare il codice',
    digits_6:  '6 cifre',
    digits_8:  '8 cifre',
    period_30:  '30 sec',
    period_60:  '60 sec',
    delete_confirm:  'Eliminare questa voce?',
    nothing_here:  'Ancora nulla qui',
    gen_title:  'Generatore di password',
    gen_copy_title:  'Copia password',
    gen_length:  'Lunghezza',
    gen_generate:  'Genera',
  },
  zh: {
    status_setup:     '需要设置',
    setup_hint:       '输入中继服务器地址以开始使用。',
    btn_open_settings:'打开设置',
    status_locked:    '密码库已锁定',
    locked_hint:      '打开手机上的 fortispass 应用并扫描二维码以解锁。',
    btn_show_qr:      '显示二维码',
    expires_in:       '过期时间',
    qr_hint:          '用 Android 应用扫描 → 生物识别 → 完成。',
    btn_cancel:       '取消',
    status_unlocked:  '密码库已解锁',
    btn_retry:        '重试',
    autolock_in:      '约 ~',
    autolock_min_unit:' 分钟后自动锁定',
    autolock_close:   '关闭浏览器时锁定',
    status_biometric: '等待生物识别',
    biometric_hint: '正在等待手机上的生物识别确认…',
    tab_passwords:  '密码',
    tab_totp:  '两步验证',
    btn_add_password:  '＋ 添加密码',
    btn_add_totp:  '＋ 添加 TOTP',
    form_add_password:  '添加密码',
    form_edit_password:  '编辑密码',
    form_add_totp:  '添加 TOTP',
    form_edit_totp:  '编辑 TOTP',
    cf_name_ph:  '名称（如 GitHub）',
    cf_url_ph:  '网址（如 https://github.com）',
    cf_username_ph:  '用户名 / 邮箱',
    cf_password_ph:  '密码',
    tf_name_ph:  '名称（如 GitHub）',
    tf_secret_ph:  '密钥（Base32）',
    btn_save:  '保存',
    copy_password_title:  '点击复制密码',
    copy_code_title:  '点击复制验证码',
    digits_6:  '6位',
    digits_8:  '8位',
    period_30:  '30秒',
    period_60:  '60秒',
    delete_confirm:  '删除此条目？',
    nothing_here:  '暂无内容',
    gen_title:  '密码生成器',
    gen_copy_title:  '复制密码',
    gen_length:  '长度',
    gen_generate:  '生成',
  },
  ru: {
    status_setup:     'Требуется настройка',
    setup_hint:       'Введите URL сервера-ретранслятора для начала работы.',
    btn_open_settings:'Открыть настройки',
    status_locked:    'Хранилище заблокировано',
    locked_hint:      'Откройте приложение fortispass на телефоне и отсканируйте QR-код.',
    btn_show_qr:      'Показать QR-код',
    expires_in:       'Истекает через',
    qr_hint:          'Отсканируйте приложением Android → биометрия → готово.',
    btn_cancel:       'Отмена',
    status_unlocked:  'Хранилище разблокировано',
    btn_retry:        'Повторить',
    autolock_in:      'Блокировка через ~',
    autolock_min_unit:' мин',
    autolock_close:   'Блокируется при закрытии браузера',
    status_biometric: 'Ожидание биометрии',
    biometric_hint: 'Ожидание биометрического подтверждения на вашем телефоне…',
    tab_passwords:  'Пароли',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ Добавить пароль',
    btn_add_totp:  '＋ Добавить TOTP',
    form_add_password:  'Добавить пароль',
    form_edit_password:  'Изменить пароль',
    form_add_totp:  'Добавить TOTP',
    form_edit_totp:  'Изменить TOTP',
    cf_name_ph:  'Название (напр. GitHub)',
    cf_url_ph:  'URL (напр. https://github.com)',
    cf_username_ph:  'Логин / эл. почта',
    cf_password_ph:  'Пароль',
    tf_name_ph:  'Название (напр. GitHub)',
    tf_secret_ph:  'Секретный ключ (Base32)',
    btn_save:  'Сохранить',
    copy_password_title:  'Нажмите для копирования пароля',
    copy_code_title:  'Нажмите для копирования кода',
    digits_6:  '6 цифр',
    digits_8:  '8 цифр',
    period_30:  '30 сек',
    period_60:  '60 сек',
    delete_confirm:  'Удалить эту запись?',
    nothing_here:  'Пока ничего нет',
    gen_title:  'Генератор паролей',
    gen_copy_title:  'Скопировать пароль',
    gen_length:  'Длина',
    gen_generate:  'Сгенерировать',
  },
  ja: {
    status_setup:     'セットアップが必要です',
    setup_hint:       'リレーサーバーのURLを入力してください。',
    btn_open_settings:'設定を開く',
    status_locked:    'ボルトはロック中',
    locked_hint:      'スマートフォンのfortispass アプリでQRコードをスキャンしてください。',
    btn_show_qr:      'QRコードを表示',
    expires_in:       '有効期限',
    qr_hint:          'Androidアプリでスキャン → 生体認証 → 完了。',
    btn_cancel:       'キャンセル',
    status_unlocked:  'ボルトはロック解除済み',
    btn_retry:        '再試行',
    autolock_in:      '約~',
    autolock_min_unit:'分後に自動ロック',
    autolock_close:   'ブラウザを閉じるとロック',
    status_biometric: '生体認証を待機中',
    biometric_hint: '携帯電話での生体認証確認を待っています…',
    tab_passwords:  'パスワード',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ パスワードを追加',
    btn_add_totp:  '＋ TOTPを追加',
    form_add_password:  'パスワードを追加',
    form_edit_password:  'パスワードを編集',
    form_add_totp:  'TOTPを追加',
    form_edit_totp:  'TOTPを編集',
    cf_name_ph:  '名前（例：GitHub）',
    cf_url_ph:  'URL（例：https://github.com）',
    cf_username_ph:  'ユーザー名 / メール',
    cf_password_ph:  'パスワード',
    tf_name_ph:  '名前（例：GitHub）',
    tf_secret_ph:  '秘密鍵（Base32）',
    btn_save:  '保存',
    copy_password_title:  'クリックでパスワードをコピー',
    copy_code_title:  'クリックでコードをコピー',
    digits_6:  '6桁',
    digits_8:  '8桁',
    period_30:  '30秒',
    period_60:  '60秒',
    delete_confirm:  'このエントリを削除しますか？',
    nothing_here:  'まだ何もありません',
    gen_title:  'パスワードジェネレーター',
    gen_copy_title:  'パスワードをコピー',
    gen_length:  '長さ',
    gen_generate:  '生成',
  },
  fr: {
    status_setup:     'Configuration requise',
    setup_hint:       'Entrez l\'URL du serveur relais pour commencer.',
    btn_open_settings:'Ouvrir les paramètres',
    status_locked:    'Coffre verrouillé',
    locked_hint:      'Ouvrez l\'app fortispass sur votre téléphone et scannez le QR code.',
    btn_show_qr:      'Afficher le QR code',
    expires_in:       'Expire dans',
    qr_hint:          'Scannez avec l\'app Android → biométrie → terminé.',
    btn_cancel:       'Annuler',
    status_unlocked:  'Coffre déverrouillé',
    btn_retry:        'Réessayer',
    autolock_in:      'Verrouillage dans ~',
    autolock_min_unit:' min',
    autolock_close:   'Se verrouille à la fermeture du navigateur',
    status_biometric: 'Attente biométrique',
    biometric_hint: 'En attente de confirmation biométrique sur votre téléphone…',
    tab_passwords:  'Mots de passe',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ Ajouter un mot de passe',
    btn_add_totp:  '＋ Ajouter TOTP',
    form_add_password:  'Ajouter un mot de passe',
    form_edit_password:  'Modifier le mot de passe',
    form_add_totp:  'Ajouter TOTP',
    form_edit_totp:  'Modifier TOTP',
    cf_name_ph:  'Nom (ex. GitHub)',
    cf_url_ph:  'URL (ex. https://github.com)',
    cf_username_ph:  'Nom d\'utilisateur / email',
    cf_password_ph:  'Mot de passe',
    tf_name_ph:  'Nom (ex. GitHub)',
    tf_secret_ph:  'Clé secrète (Base32)',
    btn_save:  'Enregistrer',
    copy_password_title:  'Cliquer pour copier le mot de passe',
    copy_code_title:  'Cliquer pour copier le code',
    digits_6:  '6 chiffres',
    digits_8:  '8 chiffres',
    period_30:  '30 sec',
    period_60:  '60 sec',
    delete_confirm:  'Supprimer cette entrée ?',
    nothing_here:  'Rien ici pour l\'instant',
    gen_title:  'Générateur de mots de passe',
    gen_copy_title:  'Copier le mot de passe',
    gen_length:  'Longueur',
    gen_generate:  'Générer',
  },
  ar: {
    status_setup:     'الإعداد مطلوب',
    setup_hint:       'أدخل عنوان URL لخادم الترحيل للبدء.',
    btn_open_settings:'فتح الإعدادات',
    status_locked:    'الخزنة مقفلة',
    locked_hint:      'افتح تطبيق fortispass على هاتفك وامسح رمز QR.',
    btn_show_qr:      'عرض رمز QR',
    expires_in:       'تنتهي خلال',
    qr_hint:          'امسح بتطبيق Android ← بيومتري ← تم.',
    btn_cancel:       'إلغاء',
    status_unlocked:  'الخزنة مفتوحة',
    btn_retry:        'إعادة المحاولة',
    autolock_in:      'قفل تلقائي خلال ~',
    autolock_min_unit:' د',
    autolock_close:   'يُقفل عند إغلاق المتصفح',
    status_biometric: 'انتظار البيومتري',
    biometric_hint: 'في انتظار التأكيد البيومتري على هاتفك…',
    tab_passwords:  'كلمات المرور',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ إضافة كلمة مرور',
    btn_add_totp:  '＋ إضافة TOTP',
    form_add_password:  'إضافة كلمة مرور',
    form_edit_password:  'تعديل كلمة المرور',
    form_add_totp:  'إضافة TOTP',
    form_edit_totp:  'تعديل TOTP',
    cf_name_ph:  'الاسم (مثال: GitHub)',
    cf_url_ph:  'الرابط (مثال: https://github.com)',
    cf_username_ph:  'اسم المستخدم / البريد',
    cf_password_ph:  'كلمة المرور',
    tf_name_ph:  'الاسم (مثال: GitHub)',
    tf_secret_ph:  'المفتاح السري (Base32)',
    btn_save:  'حفظ',
    copy_password_title:  'انقر لنسخ كلمة المرور',
    copy_code_title:  'انقر لنسخ الرمز',
    digits_6:  '٦ أرقام',
    digits_8:  '٨ أرقام',
    period_30:  '٣٠ ثانية',
    period_60:  '٦٠ ثانية',
    delete_confirm:  'حذف هذا الإدخال؟',
    nothing_here:  'لا شيء هنا بعد',
    gen_title:  'مولّد كلمات المرور',
    gen_copy_title:  'نسخ كلمة المرور',
    gen_length:  'الطول',
    gen_generate:  'توليد',
  },
  hi: {
    status_setup:     'सेटअप आवश्यक है',
    setup_hint:       'शुरू करने के लिए रिले सर्वर URL दर्ज करें।',
    btn_open_settings:'सेटिंग खोलें',
    status_locked:    'वॉल्ट लॉक है',
    locked_hint:      'अपने फ़ोन पर fortispass ऐप खोलें और QR कोड स्कैन करें।',
    btn_show_qr:      'QR कोड दिखाएं',
    expires_in:       'समाप्ति',
    qr_hint:          'Android ऐप से स्कैन करें → बायोमेट्रिक → हो गया।',
    btn_cancel:       'रद्द करें',
    status_unlocked:  'वॉल्ट अनलॉक है',
    btn_retry:        'पुनः प्रयास',
    autolock_in:      '~',
    autolock_min_unit:' मिनट में ऑटो-लॉक',
    autolock_close:   'ब्राउज़र बंद होने पर लॉक होता है',
    status_biometric: 'बायोमेट्रिक की प्रतीक्षा',
    biometric_hint: 'आपके फ़ोन पर बायोमेट्रिक पुष्टि की प्रतीक्षा है…',
    tab_passwords:  'पासवर्ड',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ पासवर्ड जोड़ें',
    btn_add_totp:  '＋ TOTP जोड़ें',
    form_add_password:  'पासवर्ड जोड़ें',
    form_edit_password:  'पासवर्ड संपादित करें',
    form_add_totp:  'TOTP जोड़ें',
    form_edit_totp:  'TOTP संपादित करें',
    cf_name_ph:  'नाम (जैसे GitHub)',
    cf_url_ph:  'URL (जैसे https://github.com)',
    cf_username_ph:  'उपयोगकर्ता नाम / ईमेल',
    cf_password_ph:  'पासवर्ड',
    tf_name_ph:  'नाम (जैसे GitHub)',
    tf_secret_ph:  'गुप्त कुंजी (Base32)',
    btn_save:  'सहेजें',
    copy_password_title:  'पासवर्ड कॉपी करने के लिए क्लिक करें',
    copy_code_title:  'कोड कॉपी करने के लिए क्लिक करें',
    digits_6:  '6 अंक',
    digits_8:  '8 अंक',
    period_30:  '30 सेकंड',
    period_60:  '60 सेकंड',
    delete_confirm:  'यह प्रविष्टि हटाएं?',
    nothing_here:  'अभी कुछ नहीं है',
    gen_title:  'पासवर्ड जनरेटर',
    gen_copy_title:  'पासवर्ड कॉपी करें',
    gen_length:  'लंबाई',
    gen_generate:  'जनरेट करें',
  },
  ko: {
    status_setup:     '설정이 필요합니다',
    setup_hint:       '시작하려면 릴레이 서버 URL을 입력하세요.',
    btn_open_settings:'설정 열기',
    status_locked:    '보관함 잠김',
    locked_hint:      '휴대폰에서 fortispass 앱을 열고 QR 코드를 스캔하세요.',
    btn_show_qr:      'QR 코드 표시',
    expires_in:       '만료까지',
    qr_hint:          'Android 앱으로 스캔 → 생체 인증 → 완료.',
    btn_cancel:       '취소',
    status_unlocked:  '보관함 잠금 해제',
    btn_retry:        '다시 시도',
    autolock_in:      '약 ~',
    autolock_min_unit:'분 후 자동 잠금',
    autolock_close:   '브라우저 종료 시 잠금',
    status_biometric: '생체 인증 대기 중',
    biometric_hint: '휴대폰에서 생체 인증 확인을 기다리는 중…',
    tab_passwords:  '비밀번호',
    tab_totp:  '2FA / TOTP',
    btn_add_password:  '＋ 비밀번호 추가',
    btn_add_totp:  '＋ TOTP 추가',
    form_add_password:  '비밀번호 추가',
    form_edit_password:  '비밀번호 편집',
    form_add_totp:  'TOTP 추가',
    form_edit_totp:  'TOTP 편집',
    cf_name_ph:  '이름 (예: GitHub)',
    cf_url_ph:  'URL (예: https://github.com)',
    cf_username_ph:  '사용자 이름 / 이메일',
    cf_password_ph:  '비밀번호',
    tf_name_ph:  '이름 (예: GitHub)',
    tf_secret_ph:  '비밀 키 (Base32)',
    btn_save:  '저장',
    copy_password_title:  '클릭하여 비밀번호 복사',
    copy_code_title:  '클릭하여 코드 복사',
    digits_6:  '6자리',
    digits_8:  '8자리',
    period_30:  '30초',
    period_60:  '60초',
    delete_confirm:  '이 항목을 삭제하시겠습니까?',
    nothing_here:  '아직 아무것도 없습니다',
    gen_title:  '비밀번호 생성기',
    gen_copy_title:  '비밀번호 복사',
    gen_length:  '길이',
    gen_generate:  '생성',
  },
};

function pt(key, lang) {
  const l = POPUP_STRINGS[lang] || POPUP_STRINGS.en;
  return l[key] ?? POPUP_STRINGS.en[key] ?? key;
}

function applyPopupLang(lang) {
  const isRTL = lang === 'ar';
  document.documentElement.dir  = isRTL ? 'rtl' : 'ltr';
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const str = pt(key, lang);
    if (str) el.textContent = str;
  });
  // Translate input placeholders
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const key = el.getAttribute('data-i18n-ph');
    const str = pt(key, lang);
    if (str) el.placeholder = str;
  });
  // Translate title attributes (tooltips)
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    const str = pt(key, lang);
    if (str) el.title = str;
  });
  // Generator button tooltip (static element, no data-i18n-title)
  const btnGen = document.getElementById('btn-gen');
  if (btnGen) btnGen.title = pt('gen_title', lang);
}

// ── Theme ─────────────────────────────────────────────────────────────────────
function applyCustomThemeVars(base, accent) {
  const root = document.documentElement;
  root.style.setProperty('--bg',    base);
  root.style.setProperty('--bg2',   shiftHex(base,  0.04));
  root.style.setProperty('--bg3',   shiftHex(base,  0.08));
  root.style.setProperty('--border',shiftHex(base,  0.16));
  root.style.setProperty('--accent',accent);
  root.style.setProperty('--accent-h', shiftHex(accent, 0.08));
  root.style.setProperty('--accent-a', shiftHex(accent, -0.08));
  // Luminance-aware text: shift toward opposite end of lightness scale
  const r = parseInt(base.slice(1,3),16)/255;
  const g = parseInt(base.slice(3,5),16)/255;
  const b = parseInt(base.slice(5,7),16)/255;
  const lum = 0.2126*r + 0.7152*g + 0.0722*b;
  const isLight = lum > 0.4;
  // On light bg: shift text DOWN (negative = darker). On dark bg: shift UP (positive = lighter).
  root.style.setProperty('--text',  shiftHex(base, isLight ? -0.75 : 0.88));
  root.style.setProperty('--text2', shiftHex(base, isLight ? -0.40 : 0.55));
  root.style.setProperty('--text3', shiftHex(base, isLight ? -0.20 : 0.32));
  root.style.setProperty('--fp-pass-color', isLight ? '#111111' : '#ffffff');
}
function shiftHex(hex, delta) {
  let r=parseInt(hex.slice(1,3),16)/255, g=parseInt(hex.slice(3,5),16)/255, b=parseInt(hex.slice(5,7),16)/255;
  const max=Math.max(r,g,b), min=Math.min(r,g,b); let h,s,l=(max+min)/2;
  if(max===min){h=s=0;}else{const d=max-min;s=l>0.5?d/(2-max-min):d/(max+min);switch(max){case r:h=((g-b)/d+(g<b?6:0))/6;break;case g:h=((b-r)/d+2)/6;break;default:h=((r-g)/d+4)/6;}}
  l=Math.max(0,Math.min(1,l+delta));
  const q=l<0.5?l*(1+s):l+s-l*s, p=2*l-q;
  const hue2rgb=(p,q,t)=>{if(t<0)t+=1;if(t>1)t-=1;if(t<1/6)return p+(q-p)*6*t;if(t<1/2)return q;if(t<2/3)return p+(q-p)*(2/3-t)*6;return p;};
  return '#'+[hue2rgb(p,q,h+1/3),hue2rgb(p,q,h),hue2rgb(p,q,h-1/3)].map(x=>Math.round(x*255).toString(16).padStart(2,'0')).join('');
}
function applyTheme(t) {
  if (t === 'system') {
    t = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  document.documentElement.setAttribute('data-theme', t);
}

// ── Load settings and apply on startup ───────────────────────────────────────
chrome.storage.local.get(['theme', 'language', 'animationsEnabled', 'fontSize', 'customTheme'], ({ theme, language, animationsEnabled, fontSize, customTheme }) => {
  // Animations
  if (animationsEnabled === false) {
    document.documentElement.classList.add('no-anim');
    document.documentElement.style.transitionDuration = '0s';
    document.body.style.transitionDuration = '0s';
  }
  // Font size
  if (fontSize) {
    document.documentElement.style.setProperty('--font-size', fontSize + 'px');
    document.body.style.fontSize = fontSize + 'px';
  }
  // Custom theme vars
  if (theme === 'custom' && customTheme) applyCustomThemeVars(customTheme.base, customTheme.accent);
  applyTheme(theme || 'dark');
  applyPopupLang(language || 'en');
});

// Live-update when settings change while popup is open
chrome.storage.onChanged.addListener(changes => {
  if (changes.theme)    {
    const th = changes.theme.newValue || 'dark';
    if (th === 'custom') {
      chrome.storage.local.get('customTheme', ({customTheme}) => {
        if (customTheme) applyCustomThemeVars(customTheme.base, customTheme.accent);
        applyTheme(th);
      });
    } else { applyTheme(th); }
  }
  if (changes.language) applyPopupLang(changes.language.newValue || 'en');
  if (changes.animationsEnabled) {
    const on = changes.animationsEnabled.newValue;
    document.documentElement.classList.toggle('no-anim', !on);
    const dur = on ? '' : '0s';
    document.documentElement.style.transitionDuration = dur;
    document.body.style.transitionDuration = dur;
  }
  if (changes.fontSize) {
    const px = changes.fontSize.newValue || 15;
    document.documentElement.style.setProperty('--font-size', px + 'px');
    document.body.style.fontSize = px + 'px';
  }
});

// ── QR rendering ─────────────────────────────────────────────────────────────
function renderQR(container, text) {
  container.innerHTML = '';
  if (typeof window.QRCode === 'undefined') {
    container.style.cssText = 'width:220px;height:220px;display:flex;align-items:center;justify-content:center;background:#fff;color:#c00;font:bold 12px monospace;text-align:center;padding:12px';
    container.textContent = 'lib/qrcode.js not loaded';
    return;
  }
  function stripQRAttrs() {
    container.querySelectorAll('img, canvas').forEach(el => {
      el.removeAttribute('title');
      el.removeAttribute('alt');
    });
  }
  // Watch both childList (element added) and attributes (title set after add).
  // Disconnect before stripping to prevent infinite re-entry, then reconnect.
  const observer = new MutationObserver(() => {
    observer.disconnect();
    stripQRAttrs();
    observer.observe(container, { childList: true, subtree: true, attributes: true, attributeFilter: ['title', 'alt'] });
  });
  observer.observe(container, { childList: true, subtree: true, attributes: true, attributeFilter: ['title', 'alt'] });
  new window.QRCode(container, {
    text,
    width: 220,
    height: 220,
    colorDark: '#000000',
    colorLight: '#ffffff',
    correctLevel: window.QRCode.CorrectLevel.M,
  });
  setTimeout(() => { observer.disconnect(); stripQRAttrs(); }, 300);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const VIEWS = ['setup', 'locked', 'qr', 'biometric', 'unlocked', 'error', 'loading'];

function showView(name) {
  VIEWS.forEach(v => {
    document.getElementById(`view-${v}`).classList.toggle('hidden', v !== name);
  });
  document.getElementById('btn-lock').classList.toggle('hidden', name !== 'unlocked');
}

function showError(msg) {
  document.getElementById('error-text').textContent = msg;
  showView('error');
}

function sw(msg, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('Service worker not responding.\nTry reloading at chrome://extensions')),
      timeoutMs
    );
    try {
      chrome.runtime.sendMessage(msg, response => {
        clearTimeout(timer);
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve(response || {});
      });
    } catch (e) { clearTimeout(timer); reject(e); }
  });
}

let _countdown = null;
function startCountdown(secs, onExpire) {
  clearInterval(_countdown);
  const el = document.getElementById('qr-countdown');
  el.textContent = secs + 's';
  _countdown = setInterval(() => {
    secs--;
    el.textContent = secs + 's';
    if (secs <= 0) { clearInterval(_countdown); onExpire(); }
  }, 1000);
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  showView('loading');
  try {
    const { relayURL, pinPromptSeen } = await chrome.storage.local.get(['relayURL', 'pinPromptSeen']);
    if (!relayURL) {
      // Show pin-prompt on first open, skip straight to configure on subsequent opens
      document.getElementById('setup-step-pin').classList.toggle('hidden', !!pinPromptSeen);
      document.getElementById('setup-step-configure').classList.toggle('hidden', !pinPromptSeen);
      showView('setup');
      return;
    }
    const resp = await sw({ type: 'GET_STATUS' });
    if (resp.error) { showError(resp.error); return; }
    showView(resp.locked ? 'locked' : 'unlocked');
    if (!resp.locked) { loadVault(); }
  } catch (e) {
    showError(e.message);
  }
}

// ── Show QR ───────────────────────────────────────────────────────────────────
async function showQR() {
  showView('loading');
  try {
    const { qrPayload, expirySecs, error } = await sw({ type: 'START_UNLOCK' }, 10000);
    if (error) { showError(error); return; }
    showView('qr');
    renderQR(document.getElementById('qr-container'), qrPayload);
    startCountdown(expirySecs || 45, () => showView('locked'));
  } catch (e) {
    showError(e.message);
  }
}

// ── Buttons ───────────────────────────────────────────────────────────────────
document.getElementById('btn-show-qr').addEventListener('click', showQR);
document.getElementById('btn-open-settings').addEventListener('click', () => chrome.runtime.openOptionsPage());
document.getElementById('btn-settings').addEventListener('click', () => chrome.runtime.openOptionsPage());
document.getElementById('btn-retry').addEventListener('click', init);
document.getElementById('btn-cancel').addEventListener('click', () => {
  clearInterval(_countdown);
  sw({ type: 'CANCEL_UNLOCK' }).catch(() => {});
  showView('locked');
});
document.getElementById('btn-cancel-bio').addEventListener('click', () => {
  sw({ type: 'CANCEL_UNLOCK' }).catch(() => {});
  showView('locked');
});
document.getElementById('btn-lock').addEventListener('click', async () => {
  await sw({ type: 'LOCK' }).catch(() => {});
  showView('locked');
});

// ── Pin-step buttons ──────────────────────────────────────────────────────────
function advanceToConfigure() {
  chrome.storage.local.set({ pinPromptSeen: true });
  document.getElementById('setup-step-pin').classList.add('hidden');
  document.getElementById('setup-step-configure').classList.remove('hidden');
}
document.getElementById('btn-pin-done').addEventListener('click', advanceToConfigure);
document.getElementById('btn-pin-skip').addEventListener('click', advanceToConfigure);

// ── Push events from SW ───────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener(msg => {
  if (msg.type === 'UNLOCK_COMPLETE') {
    clearInterval(_countdown);
    showView('unlocked');
    loadVault();
  } else if (msg.type === 'UNLOCK_FAILED') {
    clearInterval(_countdown);
    showError(msg.error || 'Unlock failed');
  } else if (msg.type === 'QR_EXPIRED' || msg.type === 'VAULT_LOCKED') {
    clearInterval(_countdown);
    showView('locked');
  } else if (msg.type === 'BIOMETRIC_STARTED') {
    // Phone scanned the QR — hide QR, show biometric waiting state
    clearInterval(_countdown);
    showView('biometric');
  } else if (msg.type === 'BIOMETRIC_FAILED') {
    // Biometric failed or was cancelled — go back to locked so user can retry
    clearInterval(_countdown);
    showView('locked');
  }
});


// ── Vault UI ──────────────────────────────────────────────────────────────────

let _vault = null;
let _vaultVersion = 1;
let _editingCredId = null;
let _editingTotpId = null;
let _totpTimers = {};

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

async function loadVault() {
  try {
    const resp = await sw({ type: 'GET_VAULT' });
    if (resp.locked) { showView('locked'); return; }
    if (resp.error) { console.warn('Vault load error:', resp.error); return; }
    _vault = resp.vault;
    _vaultVersion = resp.version;
    renderCredentials();
    renderTotps();
  } catch (e) {
    console.warn('loadVault error:', e);
  }
}

async function saveVault() {
  try {
    const resp = await sw({ type: 'SAVE_VAULT', vault: _vault, version: _vaultVersion });
    if (resp.error) { alert('Save failed: ' + resp.error); return false; }
    _vaultVersion = resp.version;
    return true;
  } catch (e) {
    alert('Save failed: ' + e.message);
    return false;
  }
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.vault-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.vault-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.tab;
    document.getElementById('tab-passwords').classList.toggle('hidden', target !== 'passwords');
    document.getElementById('tab-totp').classList.toggle('hidden', target !== 'totp');
    // Hide open forms
    document.getElementById('cred-form').classList.add('hidden');
    document.getElementById('totp-form').classList.add('hidden');
  });
});

// ── Credentials ───────────────────────────────────────────────────────────────

// Favicon loader — CSP forbids inline onerror= so we wire it here.
// Shows favicon image if it loads successfully, falls back to initials text.
function _loadFavicon(iconEl, url) {
  if (!iconEl || !url) return;
  let host;
  try { host = new URL(url).hostname; } catch { return; }
  if (!host) return;
  const img = document.createElement('img');
  img.className = 'cred-favicon';
  img.alt = '';
  img.addEventListener('load', () => {
    iconEl.textContent = '';
    iconEl.appendChild(img);
  });
  img.addEventListener('error', () => { /* keep initials */ });
  img.src = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=32`;
}

function renderCredentials() {
  if (!_vault) return;
  const lang = document.documentElement.lang || 'en';
  const list = document.getElementById('cred-list');
  list.innerHTML = '';
  (_vault.credentials || []).forEach(cred => {
    const row = document.createElement('div');
    row.className = 'cred-row';
    row.title = pt('copy_password_title', lang);
    const initials = (cred.name || '?').slice(0, 2).toUpperCase();
    row.innerHTML = `
      <div class="cred-icon" data-initials="${initials}">${initials}</div>
      <div class="cred-info">
        <div class="cred-name">${escHtml(cred.name || '')}</div>
        <div class="cred-user">${escHtml(cred.username || '')}</div>
      </div>
      <div class="cred-actions">
        <button class="cred-action-btn" data-action="edit" title="Edit">✎</button>
        <button class="cred-action-btn danger" data-action="delete" title="Delete">✕</button>
      </div>`;
    row.addEventListener('click', e => {
      if (e.target.closest('.cred-action-btn')) return;
      copyText(cred.password || '', row);
    });
    row.querySelector('[data-action="edit"]').addEventListener('click', e => {
      e.stopPropagation(); openCredForm(cred);
    });
    row.querySelector('[data-action="delete"]').addEventListener('click', async e => {
      e.stopPropagation();
      if (!confirm(pt('delete_confirm', lang))) return;
      _vault.credentials = _vault.credentials.filter(c => c.id !== cred.id);
      if (await saveVault()) renderCredentials();
    });
    // Load favicon after DOM is ready — CSP blocks inline onerror=
    if (cred.url) _loadFavicon(row.querySelector('.cred-icon'), cred.url);
    list.appendChild(row);
  });
  if ((_vault.credentials || []).length === 0) {
    const empty = document.createElement('div');
    empty.className = 'item-list-empty';
    empty.textContent = pt('nothing_here', lang);
    list.appendChild(empty);
  }
}

function openCredForm(cred = null) {
  const lang = document.documentElement.lang || 'en';
  _editingCredId = cred ? cred.id : null;
  document.getElementById('cred-form-title').textContent = pt(cred ? 'form_edit_password' : 'form_add_password', lang);
  document.getElementById('cred-form-title').removeAttribute('data-i18n');
  document.getElementById('cf-name').value     = cred?.name     || '';
  document.getElementById('cf-url').value      = cred?.url      || '';
  document.getElementById('cf-username').value = cred?.username || '';
  document.getElementById('cf-password').value = cred?.password || '';
  document.getElementById('cred-form').classList.remove('hidden');
  document.getElementById('totp-form').classList.add('hidden');
  document.getElementById('cf-name').focus();
}

document.getElementById('btn-add-cred').addEventListener('click', () => openCredForm());

document.getElementById('cf-save').addEventListener('click', async () => {
  const name     = document.getElementById('cf-name').value.trim();
  const url      = document.getElementById('cf-url').value.trim();
  const username = document.getElementById('cf-username').value.trim();
  const password = document.getElementById('cf-password').value;
  if (!name) { document.getElementById('cf-name').focus(); return; }
  if (_editingCredId) {
    const cred = _vault.credentials.find(c => c.id === _editingCredId);
    if (cred) Object.assign(cred, { name, url, username, password });
  } else {
    _vault.credentials.push({ id: uid(), name, url, username, password });
  }
  if (await saveVault()) {
    renderCredentials();
    document.getElementById('cred-form').classList.add('hidden');
  }
});

document.getElementById('cf-cancel').addEventListener('click', () => {
  document.getElementById('cred-form').classList.add('hidden');
});

document.getElementById('cf-toggle-pw').addEventListener('click', () => {
  const inp = document.getElementById('cf-password');
  inp.type = inp.type === 'password' ? 'text' : 'password';
});

// ── TOTPs ─────────────────────────────────────────────────────────────────────

function renderTotps() {
  if (!_vault) return;
  const lang = document.documentElement.lang || 'en';
  // Clear existing timers
  Object.values(_totpTimers).forEach(clearInterval);
  _totpTimers = {};
  const list = document.getElementById('totp-list');
  list.innerHTML = '';
  (_vault.totps || []).forEach(totp => {
    const row = document.createElement('div');
    row.className = 'totp-row';
    row.title = pt('copy_code_title', lang);
    const period = totp.period || 30;
    const totpInitials = (totp.name || '?').slice(0, 2).toUpperCase();
    row.innerHTML = `
      <div class="totp-info">
        <div class="totp-name">${escHtml(totp.name || '')}</div>
        <div class="totp-code" id="totp-code-${totp.id}">••••••</div>
      </div>
      <div class="totp-right">
        <div class="totp-timer" title="Seconds remaining">
          <svg width="28" height="28" viewBox="0 0 28 28">
            <circle cx="14" cy="14" r="11" fill="none" stroke="var(--bg3)" stroke-width="3"/>
            <circle id="totp-arc-${totp.id}" cx="14" cy="14" r="11" fill="none"
              stroke="var(--accent)" stroke-width="3"
              stroke-dasharray="69.1" stroke-dashoffset="0"/>
          </svg>
          <div class="totp-timer-text" id="totp-secs-${totp.id}"></div>
        </div>
        <div class="totp-actions">
          <button class="cred-action-btn" data-action="edit" title="Edit">✎</button>
          <button class="cred-action-btn danger" data-action="delete" title="Delete">✕</button>
        </div>
      </div>`;

    const updateCode = async () => {
      try {
        const resp = await sw({ type: 'GET_TOTP', secret: totp.secret, digits: totp.digits || 6, period, algorithm: totp.algorithm || 'SHA-1' });
        if (resp.code) {
          const el = document.getElementById(`totp-code-${totp.id}`);
          if (el) el.textContent = resp.code;
        }
        const rem = resp.remaining || (period - Math.floor(Date.now() / 1000) % period);
        const arc = document.getElementById(`totp-arc-${totp.id}`);
        const sec = document.getElementById(`totp-secs-${totp.id}`);
        if (arc) arc.style.strokeDashoffset = (69.1 * (1 - rem / period)).toFixed(2);
        if (sec) sec.textContent = rem;
      } catch {}
    };

    updateCode();
    _totpTimers[totp.id] = setInterval(updateCode, 1000);

    row.addEventListener('click', e => {
      if (e.target.closest('.cred-action-btn')) return;
      const code = document.getElementById(`totp-code-${totp.id}`)?.textContent;
      if (code && code !== '••••••') copyText(code, row);
    });
    row.querySelector('[data-action="edit"]').addEventListener('click', e => {
      e.stopPropagation(); openTotpForm(totp);
    });
    row.querySelector('[data-action="delete"]').addEventListener('click', async e => {
      e.stopPropagation();
      if (!confirm(pt('delete_confirm', lang))) return;
      clearInterval(_totpTimers[totp.id]);
      delete _totpTimers[totp.id];
      _vault.totps = _vault.totps.filter(t => t.id !== totp.id);
      if (await saveVault()) renderTotps();
    });
    list.appendChild(row);
  });
  if ((_vault.totps || []).length === 0) {
    const empty = document.createElement('div');
    empty.className = 'item-list-empty';
    empty.textContent = pt('nothing_here', lang);
    list.appendChild(empty);
  }
}

function openTotpForm(totp = null) {
  const lang = document.documentElement.lang || 'en';
  _editingTotpId = totp ? totp.id : null;
  document.getElementById('totp-form-title').textContent = pt(totp ? 'form_edit_totp' : 'form_add_totp', lang);
  document.getElementById('totp-form-title').removeAttribute('data-i18n');
  document.getElementById('tf-name').value   = totp?.name   || '';
  document.getElementById('tf-secret').value = totp?.secret || '';
  document.getElementById('tf-digits').value = String(totp?.digits || 6);
  document.getElementById('tf-period').value = String(totp?.period || 30);
  document.getElementById('totp-form').classList.remove('hidden');
  document.getElementById('cred-form').classList.add('hidden');
  document.getElementById('tf-name').focus();
}

document.getElementById('btn-add-totp').addEventListener('click', () => openTotpForm());

document.getElementById('tf-save').addEventListener('click', async () => {
  const name   = document.getElementById('tf-name').value.trim();
  const secret = document.getElementById('tf-secret').value.trim().replace(/\s/g, '').toUpperCase();
  const digits = parseInt(document.getElementById('tf-digits').value);
  const period = parseInt(document.getElementById('tf-period').value);
  if (!name)   { document.getElementById('tf-name').focus(); return; }
  if (!secret) { document.getElementById('tf-secret').focus(); return; }
  if (_editingTotpId) {
    const totp = _vault.totps.find(t => t.id === _editingTotpId);
    if (totp) Object.assign(totp, { name, secret, digits, period });
  } else {
    _vault.totps.push({ id: uid(), name, secret, digits, period, algorithm: 'SHA-1' });
  }
  if (await saveVault()) {
    renderTotps();
    document.getElementById('totp-form').classList.add('hidden');
  }
});

document.getElementById('tf-cancel').addEventListener('click', () => {
  document.getElementById('totp-form').classList.add('hidden');
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function copyText(text, flashEl) {
  navigator.clipboard.writeText(text).catch(() => {});
  if (flashEl) {
    flashEl.classList.add('copy-flash');
    setTimeout(() => flashEl.classList.remove('copy-flash'), 600);
  }
}

// ── Password Generator ────────────────────────────────────────────────────────

const _GEN = {
  upper:   'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  lower:   'abcdefghijklmnopqrstuvwxyz',
  digits:  '0123456789',
  symbols: '!@#$%^&*()-_=+[]{}|;:,.<>?',
};

function _buildPassword() {
  const enabled = ['upper','lower','digits','symbols'].filter(
    k => document.getElementById('gen-' + k).checked
  );
  if (!enabled.length) enabled.push('lower', 'digits');

  const pool = enabled.map(k => _GEN[k]).join('');
  const len  = parseInt(document.getElementById('gen-length').value);

  // Fill array with cryptographically random picks from pool
  const rnd   = new Uint32Array(len + enabled.length);
  crypto.getRandomValues(rnd);
  const chars = Array.from({ length: len }, (_, i) => pool[rnd[i] % pool.length]);

  // Guarantee at least one character from each enabled charset
  enabled.forEach((k, i) => {
    const set = _GEN[k];
    chars[rnd[len + i] % len] = set[rnd[i] % set.length];
  });

  // Shuffle (Fisher-Yates with crypto random)
  const shuf = new Uint32Array(len);
  crypto.getRandomValues(shuf);
  for (let i = len - 1; i > 0; i--) {
    const j = shuf[i] % (i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }

  return chars.join('');
}

function _genRefresh() {
  document.getElementById('gen-output').textContent = _buildPassword();
}

// Toggle generator panel
document.getElementById('btn-gen').addEventListener('click', () => {
  const panel = document.getElementById('gen-panel');
  const opening = panel.classList.contains('hidden');
  panel.classList.toggle('hidden', !opening);
  if (opening) _genRefresh();
});

document.getElementById('gen-generate').addEventListener('click', _genRefresh);

document.getElementById('gen-copy').addEventListener('click', () => {
  const pw = document.getElementById('gen-output').textContent;
  if (pw === '—') return;
  navigator.clipboard.writeText(pw).catch(() => {});
  const btn = document.getElementById('gen-copy');
  btn.classList.add('gen-copy-ok');
  setTimeout(() => btn.classList.remove('gen-copy-ok'), 700);
});

document.getElementById('gen-length').addEventListener('input', function() {
  document.getElementById('gen-length-val').value = this.value;
  _genRefresh();
});

document.getElementById('gen-length-val').addEventListener('input', function() {
  let v = parseInt(this.value);
  if (isNaN(v)) return;
  if (v > 64) { v = 64; this.value = 64; }
  if (v >= 8) {
    document.getElementById('gen-length').value = v;
    _genRefresh();
  }
});

document.getElementById('gen-length-val').addEventListener('blur', function() {
  let v = parseInt(this.value);
  if (isNaN(v) || v < 8) v = 8;
  if (v > 64) v = 64;
  this.value = v;
  document.getElementById('gen-length').value = v;
  _genRefresh();
});

['gen-upper','gen-lower','gen-digits','gen-symbols'].forEach(id =>
  document.getElementById(id).addEventListener('change', _genRefresh)
);


init();
