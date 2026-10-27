import { vi } from 'vitest';

// Mock console methods to avoid noise in tests
global.console = {
  ...console,
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};
