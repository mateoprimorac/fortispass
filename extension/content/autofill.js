/**
 * autofill.js — Content script. Isolated from service worker.
 * Cannot access VaultKey or decrypted data. Only sends messages to SW.
 */
'use strict';

(function () {
  if (window.location.protocol !== 'https:') return;
  if (!document.querySelector('input[type="password"]')) return;

  const domain = window.location.hostname;

  chrome.runtime.sendMessage(
    { type: 'GET_CREDENTIALS', domain },
    (response) => {
      if (chrome.runtime.lastError || !response?.credentials?.length) return;
      _showAutofillUI(response.credentials);
    }
  );

  function _showAutofillUI(credentials) {
    // Shadow DOM isolates our UI from page CSS
    const host = document.createElement('div');
    host.style.cssText = 'position:fixed;top:16px;right:16px;z-index:2147483647';
    const shadow = host.attachShadow({ mode: 'closed' });
    document.body.appendChild(host);

    const container = document.createElement('div');
    container.style.cssText =
      'position:relative;background:#1a1a2e;border:1px solid #4a4a8a;border-radius:8px;padding:8px;font-family:system-ui;min-width:200px';

    const title = document.createElement('div');
    title.style.cssText = 'color:#8888cc;font-size:11px;margin-bottom:6px;padding:0 4px';
    title.textContent = 'fortispass';
    container.appendChild(title);

    credentials.forEach(cred => {
      const btn = document.createElement('button');
      btn.style.cssText =
        'display:block;width:100%;text-align:left;background:transparent;border:none;' +
        'color:#e0e0ff;padding:6px 8px;cursor:pointer;border-radius:4px;font-size:13px';
      btn.textContent = cred.name || cred.username;
      btn.onmouseenter = () => (btn.style.background = '#2a2a4e');
      btn.onmouseleave = () => (btn.style.background = 'transparent');
      btn.addEventListener('click', () => {
        // Send only the credential ID — the SW injects credentials directly into
        // the DOM via chrome.scripting.executeScript so they never come back here.
        chrome.runtime.sendMessage(
          { type: 'FILL_CREDENTIAL', credentialID: cred.id },
          () => { document.body.removeChild(host); }
        );
      });
      container.appendChild(btn);
    });

    const close = document.createElement('button');
    close.style.cssText =
      'position:absolute;top:6px;right:8px;background:none;border:none;color:#8888cc;cursor:pointer;font-size:16px';
    close.textContent = '×';
    close.addEventListener('click', () => document.body.removeChild(host));
    container.appendChild(close);

    shadow.appendChild(container);
  }

})();
