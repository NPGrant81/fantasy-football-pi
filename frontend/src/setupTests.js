import '@testing-library/jest-dom'

// Provide a basic mock for localStorage in case the environment is missing it
if (!global.localStorage) {
  const storage = {}
  global.localStorage = {
    getItem: (key) => (key in storage ? storage[key] : null),
    setItem: (key, value) => (storage[key] = String(value)),
    removeItem: (key) => delete storage[key],
    clear: () => Object.keys(storage).forEach(k => delete storage[k]),
  }
}
