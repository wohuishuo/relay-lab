for (const form of document.querySelectorAll('form[data-opening]')) {
  form.addEventListener('submit', () => {
    form.querySelector('[data-opening-status]').textContent = '正在建立私有连接…';
  });
}
for (const form of document.querySelectorAll('form[data-panel]')) {
  form.addEventListener('submit', async (event) => {
    const submitter = event.submitter;
    if (!submitter) return;
    event.preventDefault();
    if (form.getAttribute('aria-busy') === 'true') return;
    const data = new FormData(form);
    data.set('action', submitter.value);
    const result = document.getElementById('result-' + form.dataset.panel);
    const buttons = form.querySelectorAll('button');
    function show(state, summary, detail = '', stamp = '') {
      result.dataset.state = state;
      result.querySelector('[data-summary]').textContent = summary;
      result.querySelector('[data-detail]').textContent = detail;
      result.querySelector('[data-stamp]').textContent = stamp;
    }
    form.setAttribute('aria-busy', 'true');
    for (const button of buttons) button.disabled = true;
    const start = Date.now();
    show('pending', form.dataset.pending, '请稍候。');
    const timer = setInterval(() => {
      result.querySelector('[data-stamp]').textContent = '已等待 ' + Math.floor((Date.now() - start) / 1000) + ' 秒';
    }, 1000);
    try {
      const reply = await fetch(form.getAttribute('action'), {method:'POST', body:data, headers:{Accept:'application/json'}, credentials:'same-origin'});
      if (reply.redirected || reply.status === 403) {
        show('error', '本次操作未能验证身份', '请重新打开节点运维页并登录。');
      } else if (!reply.ok) {
        show('error', '工作台请求未完成', 'HTTP ' + reply.status + '。请先检查状态。');
      } else {
        const outcome = await reply.json();
        show(outcome.state, outcome.summary, outcome.detail, outcome.stamp);
      }
    } catch {
      show('error', '未收到工作台结果', form.dataset.panel === 'maintenance'
        ? '请先读取服务器状态，再决定是否重新提交。' : '请确认工作台仍在运行，然后重试。');
    } finally {
      clearInterval(timer);
      form.removeAttribute('aria-busy');
      for (const button of buttons) button.disabled = false;
    }
  });
}
