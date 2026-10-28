/*
 * help-dialog hook
 * After a visitor has stayed on the page for more than 10 seconds, show a
 * "How can I help?" dialog with a message box. Sending the message opens a
 * second, native browser dialog to confirm. Shown once per browser session.
 * Time only counts while the tab is visible.
 *
 * Source of truth for the snippet inlined at the end of index.html
 * (the Pages workflow excludes dotfiles, so this file is not deployed itself).
 */
(function () {
  var DELAY_MS = 10000;
  var KEY = 'helpDialogShown';

  try { if (sessionStorage.getItem(KEY)) return; } catch (e) {}

  var timer = null;
  var remaining = DELAY_MS;
  var startedAt = 0;

  function start() {
    if (timer || document.hidden) return;
    startedAt = Date.now();
    timer = setTimeout(show, remaining);
  }
  function pause() {
    if (!timer) return;
    clearTimeout(timer);
    timer = null;
    remaining = Math.max(0, remaining - (Date.now() - startedAt));
  }

  function show() {
    timer = null;
    document.removeEventListener('visibilitychange', onVis);
    try { sessionStorage.setItem(KEY, '1'); } catch (e) {}

    var dlg = document.createElement('dialog');
    dlg.setAttribute('aria-labelledby', 'help-dialog-title');
    dlg.style.cssText = 'border:0;border-radius:12px;padding:24px;max-width:min(90vw,380px);' +
      'box-shadow:0 10px 40px rgba(0,0,0,.3);font:inherit;color:#222;background:#fff';

    var title = document.createElement('h2');
    title.id = 'help-dialog-title';
    title.textContent = 'How can I help?';
    title.style.cssText = 'margin:0 0 12px;font-size:1.25rem';

    var box = document.createElement('textarea');
    box.rows = 3;
    box.setAttribute('aria-label', 'Your message');
    box.placeholder = 'Type your question here...';
    box.style.cssText = 'width:100%;box-sizing:border-box;padding:8px;font:inherit;' +
      'border:1px solid #bbb;border-radius:8px;resize:vertical';

    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;margin-top:12px';

    function button(label, primary) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = label;
      b.style.cssText = 'padding:8px 16px;border-radius:8px;font:inherit;cursor:pointer;' +
        (primary ? 'border:0;background:#1a73e8;color:#fff' : 'border:1px solid #bbb;background:#fff;color:#222');
      return b;
    }
    var close = button('Close', false);
    var send = button('Send', true);

    close.addEventListener('click', function () { dlg.close(); });
    send.addEventListener('click', function () {
      var text = box.value.trim();
      dlg.close();
      // Second dialog: native browser dialog box.
      window.alert(text
        ? 'Thanks! We received your message:\n\n' + text
        : 'Thanks for stopping by! Let us know if you need anything.');
    });
    dlg.addEventListener('close', function () { dlg.remove(); });

    row.append(close, send);
    dlg.append(title, box, row);
    document.body.appendChild(dlg);

    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');
    box.focus();
  }

  function onVis() { document.hidden ? pause() : start(); }
  document.addEventListener('visibilitychange', onVis);
  start();
})();
