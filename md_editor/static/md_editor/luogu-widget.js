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

  // ---- 本地草稿 ----
  //
  // 上游的草稿键是全局的，A 帖的草稿会串进 B 帖的表单，所以这里按
  // 「页面路径 + 字段名」命名空间化：/posts/create/ 与 /posts/5/ 的评论框互不干扰。
  // 提交时清掉；校验失败时服务端会把内容重新渲染回字段里，所以不会丢。
  // 草稿只存在本机浏览器，不涉及服务端。

  var DRAFT_PREFIX = 'lmd_draft:';
  var draftKey = '';
  var initialContent = '';
  var draftTimer = null;

  function draftStorageKey() {
    var field = root.querySelector('#editorTextarea');
    var name = (field && field.name) || 'content';
    return DRAFT_PREFIX + location.pathname + ':' + name;
  }

  function readDraft() {
    try {
      return window.localStorage.getItem(draftKey) || '';
    } catch (err) {
      return '';
    }
  }

  function writeDraft(text) {
    try {
      // 内容跟初值一样（根本没改过）就不留草稿
      if (!text || text === initialContent) window.localStorage.removeItem(draftKey);
      else window.localStorage.setItem(draftKey, text);
    } catch (err) {
      /* 隐私模式下写不进去，忽略 */
    }
  }

  function scheduleDraftSave() {
    if (!draftKey) return;
    if (draftTimer) window.clearTimeout(draftTimer);
    draftTimer = window.setTimeout(function () {
      draftTimer = null;
      if (editor) writeDraft(editor.getContent());
      updateSaveStatus();
    }, 400);
  }

  function clearDraft() {
    if (draftTimer) {
      window.clearTimeout(draftTimer);
      draftTimer = null;
    }
    if (draftKey) writeDraft('');
  }

  function updateSaveStatus() {
    var el = document.getElementById('saveStatusIndicator');
    if (!el) return;
    el.classList.remove('save-failed');

    var hasDraft = false;
    try {
      hasDraft = !!window.localStorage.getItem(draftKey);
    } catch (err) {
      /* 忽略 */
    }
    // 说清楚「存在哪」：只在本机浏览器里，跟提交到论坛是两回事
    el.innerText = hasDraft
      ? '草稿暂存在本机浏览器，尚未提交到论坛'
      : '尚未提交，离开页面会丢失';
  }

  // ---- 本地文件操作：论坛里不适用，换成明确提示 ----

  function patchFileOperations() {
    editor.autoSave = function () {
      // 上游把「自动保存」当成本地文件应用的行为；论坛里改成
      // 「本机草稿 + 说明没提交」，两者都跟状态栏文案绑定
      updateSaveStatus();
      scheduleDraftSave();
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

  // 与服务端 md_editor.views.upload_view 的校验保持一致，先在浏览器侧拦一道给出即时反馈
  var IMAGE_MIME = /^image\/(png|jpeg|webp)$/;
  var MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

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

  /**
   * 上传一张图片并插入到光标处。
   *
   * options.alt          插入用的替代文字（缺省时取模态框里的输入或文件名）
   * options.fromModal    是否来自图片弹窗（决定是否关闭弹窗、复位文件框、写弹窗提示）
   */
  function uploadImage(file, options) {
    options = options || {};
    var fromModal = options.fromModal !== false;
    var endpoint = root.getAttribute('data-image-upload-to');
    if (!endpoint) return;

    if (!IMAGE_MIME.test(file.type)) {
      var mimeMsg = '只支持 JPG / PNG / WebP 图片，当前文件类型是 ' + (file.type || '未知') + '。';
      if (fromModal) setHint('上传失败：' + mimeMsg);
      editor.showToast(mimeMsg, 'error');
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      var sizeMsg = '图片不能超过 10 MB，当前 ' + (file.size / 1024 / 1024).toFixed(1) + ' MB。';
      if (fromModal) setHint('上传失败：' + sizeMsg);
      editor.showToast(sizeMsg, 'error');
      return;
    }

    var form = new FormData();
    form.append('image', file);
    if (fromModal) setHint('正在上传 ' + (file.name || '图片') + ' …');

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
      var alt = options.alt || (fromModal && altEl && altEl.value.trim()) || file.name || '图片';
      editor.insertAtCursor('![' + alt + '](' + result.data.url + ')');
      editor.showToast('图片已上传并插入。', 'success');
      if (fromModal) {
        editor.closeModal('imageModal');
        setHint(DEFAULT_HINT);
        var input = document.getElementById('imageFileInput');
        if (input) input.value = '';
      }
    }).catch(function (err) {
      if (fromModal) setHint('上传失败：' + err.message);
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

  // ---- 粘贴 / 拖拽上传 ----
  //
  // 写题解时最常见的动作是截图后直接 Ctrl+V，或把图片拖进编辑区。
  // 这两条路径都走同一个上传接口，只是不经过图片弹窗。

  function pickImageFile(dataTransfer) {
    if (!dataTransfer) return null;

    // 拖拽与部分浏览器的截图粘贴会带 files
    var files = dataTransfer.files;
    for (var i = 0; files && i < files.length; i++) {
      if (IMAGE_MIME.test(files[i].type)) return files[i];
    }

    // 另一些浏览器只给 items
    var items = dataTransfer.items;
    for (var j = 0; items && j < items.length; j++) {
      var item = items[j];
      if (item.kind === 'file' && IMAGE_MIME.test(item.type)) {
        var file = item.getAsFile();
        if (file) return file;
      }
    }
    return null;
  }

  function bindPasteUpload() {
    // 绑在容器上而不是 textarea：Typora 模式下编辑区是覆盖层，事件不经过 textarea
    root.addEventListener('paste', function (event) {
      var file = pickImageFile(event.clipboardData);
      if (!file) return;   // 普通文本粘贴保持原样
      event.preventDefault();
      uploadImage(file, { alt: '粘贴的图片', fromModal: false });
    });
  }

  function bindDropUpload() {
    var depth = 0;

    function hasFiles(event) {
      var types = event.dataTransfer && event.dataTransfer.types;
      for (var i = 0; types && i < types.length; i++) {
        if (types[i] === 'Files') return true;
      }
      return false;
    }

    root.addEventListener('dragenter', function (event) {
      if (!hasFiles(event)) return;
      event.preventDefault();
      depth++;
      root.classList.add('lmd-drop-active');
    });

    root.addEventListener('dragover', function (event) {
      if (!hasFiles(event)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'copy';
    });

    root.addEventListener('dragleave', function () {
      if (--depth <= 0) {
        depth = 0;
        root.classList.remove('lmd-drop-active');
      }
    });

    root.addEventListener('drop', function (event) {
      if (!hasFiles(event)) return;
      event.preventDefault();
      depth = 0;
      root.classList.remove('lmd-drop-active');

      var file = pickImageFile(event.dataTransfer);
      if (!file) {
        editor.showToast('拖入的文件里没有可用的图片（支持 JPG / PNG / WebP）。', 'error');
        return;
      }
      uploadImage(file, { alt: '拖入的图片', fromModal: false });
    });
  }

  // ---- 提交兜底 ----

  function syncOnSubmit() {
    var form = root.closest('form');
    if (!form) return;
    form.addEventListener('submit', function () {
      var textarea = root.querySelector('#editorTextarea');
      if (textarea && editor) textarea.value = editor.getContent();
      // 提交即清草稿。校验失败时服务端会把内容重新渲染回字段里，不会丢；
      // 不清的话下次打开这个页面会「恢复」已经提交过的旧内容。
      clearDraft();
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

    // 草稿键要先算出来：setContent 会触发 autoSave，那里要用到它
    initialContent = initialValue || '';
    draftKey = draftStorageKey();

    // 覆盖上游塞进来的演示模板/草稿，写回真实初值（不污染撤销历史）
    editor.setContent(initialContent, false);

    // 有本机草稿就恢复。按「页面 + 字段名」隔离，不会串到别的表单
    var draft = readDraft();
    if (draft && draft !== initialContent) {
      editor.setContent(draft, false);
      editor.showToast('已恢复上次未提交的草稿。', 'info');
    }

    applyTheme();
    watchTheme();
    patchFileOperations();
    bindImageUpload();
    bindPasteUpload();
    bindDropUpload();
    syncOnSubmit();

    // 上游的 autoSave 已被替换，这里补一次状态栏文案
    editor.autoSave();

    root.classList.add('lmd-widget-ready');
  }

  return {
    init: init,
    insertImageUrl: insertImageUrl,
    uploadImage: uploadImage,
    applyTheme: applyTheme
  };
})();
