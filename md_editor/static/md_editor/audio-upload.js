/* 音频上传：给 Markdown 编辑器补一个「插入音频」按钮。
 *
 * 编辑器本身只处理图片（工具栏按钮 + accept="image/*" 的文件选择框），
 * 而它是打包过的产物、仓库里没有对应的源码，所以这里不去动它：
 * 复用同一个上传接口，把 <audio controls src="..."> 插进编辑器的 textarea。
 *
 * 用 <audio ...> 原始 HTML 而不是自定义语法，是为了让「编辑器预览」和
 * 「发布后」看到的是同一份东西 —— 发布渲染走的 markdown-it 会把这一段
 * 原样透传，bleach 白名单也已经放行 audio/source。
 */
(function () {
  'use strict';

  var AUDIO_HTML = '<audio controls preload="metadata" src="%URL%"></audio>';

  //: 服务端错误码 → 给人看的话
  var ERROR_MESSAGES = {
    'login required': '登录状态已失效，请刷新页面后重新登录',
    'no file': '没有选中文件',
    'unsupported file type': '只支持图片，或 mp3 / ogg / wav / m4a / aac / flac 音频',
    'too large': '文件超过上限（图片 10 MB，音频 25 MB）',
  };

  function csrfToken() {
    var field = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (field && field.value) {
      return field.value;
    }
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function insertAtCursor(textarea, text) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    if (typeof start !== 'number' || typeof end !== 'number') {
      start = end = textarea.value.length;
    }

    textarea.value = textarea.value.slice(0, start) + text + textarea.value.slice(end);
    var caret = start + text.length;
    try {
      textarea.setSelectionRange(caret, caret);
    } catch (error) {
      // 某些浏览器在隐藏/未聚焦的元素上不允许设置选区，插进去就行
    }

    // 编辑器的 v-model 监听 input 事件。不派发的话内容只进了 DOM、
    // 没进编辑器内部的状态，切到预览或提交时刚插入的音频会丢。
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.focus();
  }

  function setStatus(node, message, isError) {
    if (!node) {
      return;
    }
    node.textContent = message || '';
    node.classList.toggle('text-danger', Boolean(isError));
    node.classList.toggle('text-muted', !isError);
  }

  function upload(url, file) {
    var data = new FormData();
    data.append('file', file);

    return fetch(url, {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken() },
    }).then(function (response) {
      return response.json().catch(function () {
        return {};
      }).then(function (payload) {
        if (!response.ok) {
          var code = payload.error || ('HTTP ' + response.status);
          throw new Error(ERROR_MESSAGES[code] || code);
        }
        return payload;
      });
    });
  }

  function setup(bar) {
    var scope = bar.closest('[data-md-editor-scope]') || document;
    var button = bar.querySelector('.md_editor-audio-button');
    var picker = bar.querySelector('.md_editor-audio-input');
    var status = bar.querySelector('.md_editor-audio-status');
    var textarea = scope.querySelector('.md_editor textarea');

    // 编辑器是异步挂载的，没挂上时留给 init 重试
    if (!button || !picker || !textarea) {
      return false;
    }

    var uploadUrl = bar.getAttribute('data-upload-to');

    // 挂上之后留个标记：编辑器是异步挂载的，出问题时一眼能看出
    // 是「没找到编辑器」还是「找到了但上传失败」
    bar.setAttribute('data-audio-upload-ready', 'true');

    button.addEventListener('click', function () {
      picker.click();
    });

    picker.addEventListener('change', function () {
      var file = picker.files && picker.files[0];
      if (!file) {
        return;
      }

      setStatus(status, '上传中…', false);
      button.disabled = true;

      upload(uploadUrl, file)
        .then(function (payload) {
          if (payload.kind !== 'audio') {
            throw new Error('这个文件不是音频');
          }
          insertAtCursor(textarea, AUDIO_HTML.replace('%URL%', payload.url));
          setStatus(status, '已插入音频');
        })
        .catch(function (error) {
          setStatus(status, '上传失败：' + error.message, true);
        })
        .then(function () {
          button.disabled = false;
          picker.value = '';
        });
    });

    return true;
  }

  function init() {
    var bars = document.querySelectorAll('.md_editor-audio-bar');
    var pending = [];

    for (var index = 0; index < bars.length; index++) {
      if (!setup(bars[index])) {
        pending.push(bars[index]);
      }
    }

    // 编辑器还没挂载时（脚本顺序变化、慢网络下的模块加载）再试几次
    if (pending.length && init.attempts < 20) {
      init.attempts += 1;
      window.setTimeout(function () {
        for (var i = 0; i < pending.length; i++) {
          setup(pending[i]);
        }
      }, 50);
    }
  }

  init.attempts = 0;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
