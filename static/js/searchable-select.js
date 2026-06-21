/**
 * LabManager 可搜索下拉选择器
 * 支持关键词搜索 + 分类标签过滤 + 中文输入法兼容
 */
class SearchableSelect {
  constructor(container, options = {}) {
    this.container = typeof container === 'string' ? document.querySelector(container) : container;
    if (!this.container) return;

    this.apiUrl = options.apiUrl || '/api/equipment/list';
    this.name = options.name || 'equipment_id';
    this.placeholder = options.placeholder || '搜索并选择器材…';
    this.value = options.value || '';
    this.onChange = options.onChange || (() => {});

    this.composing = false;
    this.currentCategory = 'all';
    this.selectedId = null;
    this.selectedText = '';
    this.data = [];
    this.categories = [];
    this.open = false;

    this._render();
    this._bindEvents();
    this._loadData();
  }

  _render() {
    this.container.classList.add('searchable-select');
    this.container.innerHTML = `
      <div class="ss-trigger">
        <i class="bi bi-search ss-search-icon"></i>
        <input type="text" class="ss-input" placeholder="${this.placeholder}" autocomplete="off">
        <i class="bi bi-chevron-down ss-arrow"></i>
        <input type="hidden" name="${this.name}" class="ss-value" value="${this.value}">
      </div>
      <div class="ss-dropdown">
        <div class="ss-category-tabs"></div>
        <div class="ss-options"></div>
      </div>`;
    this.input = this.container.querySelector('.ss-input');
    this.hidden = this.container.querySelector('.ss-value');
    this.dropdown = this.container.querySelector('.ss-dropdown');
    this.catTabs = this.container.querySelector('.ss-category-tabs');
    this.optionsEl = this.container.querySelector('.ss-options');
  }

  _bindEvents() {
    this.input.addEventListener('focus', () => this._open());
    this.container.querySelector('.ss-trigger').addEventListener('click', (e) => {
      if (e.target !== this.input) this.input.focus();
      this._open();
    });

    this.input.addEventListener('compositionstart', () => { this.composing = true; });
    this.input.addEventListener('compositionend', () => {
      this.composing = false;
      this._filter();
    });
    this.input.addEventListener('input', () => {
      if (!this.composing) this._filter();
    });

    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { this._close(); e.preventDefault(); }
      if (e.key === 'ArrowDown') { e.preventDefault(); this._moveHighlight(1); }
      if (e.key === 'ArrowUp') { e.preventDefault(); this._moveHighlight(-1); }
      if (e.key === 'Enter') {
        e.preventDefault();
        const hl = this.optionsEl.querySelector('.ss-option.highlighted');
        if (hl) hl.click();
      }
    });

    document.addEventListener('click', (e) => {
      if (!this.container.contains(e.target)) this._close();
    });
  }

  async _loadData() {
    try {
      const resp = await fetch(this.apiUrl);
      const json = await resp.json();
      this.data = json.equipments || [];
      this.categories = json.categories || [];
      this._renderCategories();
      this._renderOptions(this.data);
    } catch (err) {
      console.error('SearchableSelect: failed to load data', err);
    }
  }

  _renderCategories() {
    const cats = ['all', ...this.categories];
    const labels = { all: '全部', ...Object.fromEntries(this.categories.map(c => [c, c])) };
    this.catTabs.innerHTML = cats.map(c =>
      `<span class="ss-category-tab${c === 'all' ? ' active' : ''}" data-cat="${c}">${labels[c] || c}</span>`
    ).join('');

    this.catTabs.querySelectorAll('.ss-category-tab').forEach(tab => {
      tab.addEventListener('click', (e) => {
        e.stopPropagation();
        this.currentCategory = tab.dataset.cat;
        this.catTabs.querySelectorAll('.ss-category-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this._filter();
      });
    });
  }

  _filter() {
    const q = this.input.value.toLowerCase();
    let filtered = this.data;
    if (this.currentCategory !== 'all') {
      filtered = filtered.filter(e => e.category_name === this.currentCategory);
    }
    if (q) {
      filtered = filtered.filter(e =>
        e.name.toLowerCase().includes(q) || (e.model || '').toLowerCase().includes(q)
      );
    }
    this._renderOptions(filtered);
  }

  _renderOptions(items) {
    if (items.length === 0) {
      if (this.optionsEl.dataset.empty !== '1') {
        this.optionsEl.innerHTML = '<div class="ss-no-results"><i class="bi bi-inbox"></i><p>没找到匹配的器材</p></div>';
        this.optionsEl.dataset.empty = '1';
      }
      return;
    }
    this.optionsEl.dataset.empty = '0';
    var html = items.map(e => {
      const isLow = e.alert_threshold > 0 && e.stock_quantity <= e.alert_threshold;
      const sel = e.id === this.selectedId ? ' selected' : '';
      return `<div class="ss-option${sel}" data-id="${e.id}" data-name="${e.name} (${e.model || '无型号'})">
        <div class="ss-option-info">
          <span class="ss-option-name">${this._escape(e.name)}</span>
          <small class="text-muted">${this._escape(e.model || '')}</small>
          <small class="text-muted d-block">${this._escape(e.category_name || '')} · ${this._escape(e.packaging || '')}</small>
        </div>
        <span class="ss-option-stock${isLow ? ' low' : ''}">库存: ${e.stock_quantity}${e.unit || '个'}${isLow ? ' ⚠' : ''}</span>
      </div>`;
    }).join('');
    // 缓存：仅内容变化时才更新 DOM
    if (this._lastRendered !== html) {
      this._lastRendered = html;
      this.optionsEl.innerHTML = html;
    }

    this.optionsEl.querySelectorAll('.ss-option').forEach(opt => {
      opt.addEventListener('mousedown', (e) => {
        e.preventDefault();
        this._select(parseInt(opt.dataset.id), opt.dataset.name);
      });
    });
  }

  _select(id, text) {
    this.selectedId = id;
    this.selectedText = text;
    this.input.value = text;
    this.hidden.value = id;
    this._close();
    this.onChange(id, text);
    this._renderOptions(this.data.filter(e =>
      this.currentCategory === 'all' || e.category_name === this.currentCategory
    ));
  }

  _moveHighlight(dir) {
    const items = [...this.optionsEl.querySelectorAll('.ss-option')];
    if (items.length === 0) return;
    const idx = items.findIndex(o => o.classList.contains('highlighted'));
    items.forEach(o => o.classList.remove('highlighted'));
    const next = idx === -1 ? (dir > 0 ? 0 : items.length - 1)
      : Math.min(Math.max(idx + dir, 0), items.length - 1);
    items[next].classList.add('highlighted');
    items[next].scrollIntoView({ block: 'nearest' });
  }

  _open() {
    if (this.open) return;
    this.open = true;
    this.container.classList.add('open');
    this._filter();
  }

  _close() {
    this.open = false;
    this.container.classList.remove('open');
  }

  _escape(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}

// Auto-init on elements with data-searchable-select attribute
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-searchable-select]').forEach(el => {
    new SearchableSelect(el, {
      apiUrl: el.dataset.apiUrl || '/api/equipment/list',
      name: el.dataset.name || 'equipment_id',
      placeholder: el.dataset.placeholder || '搜索并选择器材…',
      value: el.dataset.value || ''
    });
  });
});
