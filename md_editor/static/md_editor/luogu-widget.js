/**
 * 洛谷 Markdown 编辑器 —— 论坛适配层
 *
 * 上游编辑器是本地文件应用，这里把它接进 Django 表单，只做四件事：
 *
 *   1. 内容：上游 init() 会塞演示模板或 localStorage 草稿，这里覆盖回表单初值；
 *      编辑器本身把内容写在 textarea 上，而该 textarea 带 name，因此
 *      原生表单提交即可，无需隐藏域同步（submit 事件里再兜一次底）。
 *   2. 主题：跟随站点的 data-bs-theme（Bootstrap），映射到上游的 light/dark。
 *   3. 本地文件操作：下拉/快捷键里的「保存到本地/打开文件/导出」在论坛里没有意义，
 *      改成提示，避免用户以为内容已经存下来了。
 *   4. 图片：上游只能填 URL，这里接上论坛的上传接口（/api/upload/）。
 */
window.LMDWidget = window.LMDWidget || (function () {
  'use strict';

  var editor = null;
  var root = null;

  // ---- 主题 ----

  function siteTheme() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
  }

  function applyTheme() {
    if (!editor) return;
    var theme = siteTheme();
    editor.setTheme(theme);
    // 上游把 data-theme 挂在 <html> 上；作用域改写后的样式要求它挂在本容器上
    if (root) root.setAttribute('data-theme', theme);
  }

  function watchTheme() {
    if (typeof MutationObserver === 'undefined') return;
    new MutationObserver(applyTheme).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-bs-theme']
    });
  }

  // ---- 本地文件操作：论坛里不适用，换成明确提示 ----

  function patchFileOperations() {
    editor.autoSave = function () {
      var el = document.getElementById('saveStatusIndicator');
      if (!el) return;
      el.classList.remove('save-failed');
      el.innerText = '尚未提交，离开页面会丢失';
    };

    function notSupported(message) {
      editor.showToast(message, 'info');
    }

    editor.newDocument = function () { notSupported('论坛编辑器不支持新建本地文档。'); };
    editor.triggerFileOpen = function () { notSupported('论坛编辑器不支持打开本地文件。'); };
    editor.saveMarkdownFile = function () { notSupported('内容还没有存到论坛，请用页面上的提交按钮。'); };
    editor.exportStandaloneHTML = function () { notSupported('论坛编辑器不支持导出 HTML。'); };
    editor.printDocument = function () { notSupported('请使用浏览器自带的打印功能。'); };
    editor.copyLuoguMarkdown = function () {
      var text = editor.getContent();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          notSupported('已复制 Markdown 源码。');
        }, function () {
          notSupported('复制失败，请手动选中复制。');
        });
      } else {
        notSupported('当前浏览器不支持一键复制。');
      }
    };
  }

  // ---- 图片上传 ----

  function csrfToken() {
    var el = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return el ? el.value : '';
  }

  function setHint(text) {
    var hint = document.getElementById('imageUploadHint');
    if (hint) hint.textContent = text;
  }

  var DEFAULT_HINT = '支持 JPG / PNG / WebP，单张不超过 10 MB；上传完成后会自动插入到光标处。';

  function insertImageUrl() {
    var altEl = document.getElementById('imageAltInput');
    var urlEl = document.getElementById('imageUrlInput');
    var alt = (altEl && altEl.value.trim()) || '图片';
    var url = urlEl && urlEl.value.trim();

    if (!url) {
      editor.showToast('请填写图片 URL，或先从本地上传一张图片。', 'error');
      return;
    }

    editor.insertAtCursor('![' + alt + '](' + url + ')');
    editor.closeModal('imageModal');
    if (urlEl) urlEl.value = '';
  }

  function uploadImage(file) {
    var endpoint = root.getAttribute('data-image-upload-to');
    if (!endpoint) return;

    var form = new FormData();
    form.append('image', file);
    setHint('正在上传 ' + file.name + ' …');

    fetch(endpoint, {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken() }
    }).then(function (response) {
      return response.json().catch(function () {
        return { error: '服务端返回了非 JSON 响应（HTTP ' + response.status + '）' };
      }).then(function (data) {
        return { ok: response.ok, data: data };
      });
    }).then(function (result) {
      if (!result.ok || !result.data.url) {
        throw new Error(result.data.error || '上传失败');
      }
      var altEl = document.getElementById('imageAltInput');
      var alt = (altEl && altEl.value.trim()) || file.name || '图片';
      editor.insertAtCursor('![' + alt + '](' + result.data.url + ')');
      editor.closeModal('imageModal');
      editor.showToast('图片已上传并插入。', 'success');
      setHint(DEFAULT_HINT);
      var input = document.getElementById('imageFileInput');
      if (input) input.value = '';
    }).catch(function (err) {
      setHint('上传失败：' + err.message);
      editor.showToast('图片上传失败：' + err.message, 'error');
    });
  }

  function bindImageUpload() {
    var input = document.getElementById('imageFileInput');
    if (!input) return;
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      if (file) uploadImage(file);
    });
  }

  // ---- 提交兜底 ----

  function syncOnSubmit() {
    var form = root.closest('form');
    if (!form) return;
    form.addEventListener('submit', function () {
      var textarea = root.querySelector('#editorTextarea');
      if (textarea && editor) textarea.value = editor.getContent();
    });
  }

  // ---- 初始化 ----

  function init(element, initialValue) {
    root = element || document.querySelector('[data-lmd-editor]');
    editor = window.LuoguEditor;

    if (!editor || !root) {
      console.error('[lmd] LuoguEditor 未就绪，编辑器无法初始化');
      return;
    }

    // 覆盖上游塞进来的演示模板/草稿，写回真实初值（不污染撤销历史）
    editor.setContent(initialValue || '', false);

    applyTheme();
    watchTheme();
    patchFileOperations();
    bindImageUpload();
    syncOnSubmit();

    // 上游的 autoSave 已被替换，这里补一次状态栏文案
    editor.autoSave();

    root.classList.add('lmd-widget-ready');
  }

  return {
    init: init,
    insertImageUrl: insertImageUrl,
    applyTheme: applyTheme
  };
})();
