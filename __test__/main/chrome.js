class Storage {
  constructor() {
    this.data = {};
  }

  get(keys, callback) {
    const result = {};
    for (const key of keys) {
      result[key] = this.data[key];
    }
    if (callback) {
      callback(result);
    }
    return result;
  }

  set(items, callback) {
    Object.assign(this.data, items);
    if (callback) {
      callback();
    }
  }

  remove(keys, callback) {
    for (const key of keys) {
      delete this.data[key];
    }
    if (callback) {
      callback();
    }
  }
}

class Chrome {
  constructor() {
    this.runtime = {
      lastError: null,
      getURL: (path) => `chrome-extension://test${path}`,
    };
    this.storage = {
      local: new Storage(),
      sync: new Storage(),
    };
  }
}

export default Chrome;
