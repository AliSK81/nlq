import http from 'k6/http';
import { check, sleep } from 'k6';

const SEARCH_URL = __ENV.SEARCH_URL || 'http://localhost:8080/search';
const CHAT_URL = __ENV.CHAT_URL || 'http://localhost:8000/v1/chat/completions';
const PROFILE = __ENV.K6_PROFILE || 'local';

// local = soak budgets; ci = short smoke against a freshly built Compose stack
const PROFILES = {
  local: {
    searchVus: 5,
    searchDuration: '30s',
    chatVus: 2,
    chatDuration: '30s',
    chatStart: '5s',
    searchP95: 2000,
    chatP95: 15000,
  },
  ci: {
    searchVus: 2,
    searchDuration: '20s',
    chatVus: 1,
    chatDuration: '15s',
    chatStart: '3s',
    searchP95: 5000,
    chatP95: 45000,
  },
};

const cfg = PROFILES[PROFILE] || PROFILES.local;

export const options = {
  scenarios: {
    search: {
      executor: 'constant-vus',
      vus: cfg.searchVus,
      duration: cfg.searchDuration,
      exec: 'search',
    },
    chat: {
      executor: 'constant-vus',
      vus: cfg.chatVus,
      duration: cfg.chatDuration,
      exec: 'chat',
      startTime: cfg.chatStart,
    },
  },
  thresholds: {
    'http_req_duration{scenario:search}': [`p(95)<${cfg.searchP95}`],
    'http_req_duration{scenario:chat}': [`p(95)<${cfg.chatP95}`],
    checks: ['rate>0.9'],
  },
};

export function search() {
  const res = http.post(
    SEARCH_URL,
    JSON.stringify({ query: 'revenue growth', top_k: 8, min_score: 0.1 }),
    { headers: { 'Content-Type': 'application/json' }, tags: { scenario: 'search' } },
  );
  check(res, { 'search status 200': (r) => r.status === 200 });
  sleep(0.5);
}

export function chat() {
  const res = http.post(
    CHAT_URL,
    JSON.stringify({
      model: 'file-qa-agent',
      messages: [{ role: 'user', content: 'What was revenue growth?' }],
      stream: false,
    }),
    { headers: { 'Content-Type': 'application/json' }, tags: { scenario: 'chat' } },
  );
  check(res, { 'chat status 200': (r) => r.status === 200 });
  sleep(1);
}
