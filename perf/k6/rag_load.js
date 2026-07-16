import http from 'k6/http';
import { check, sleep } from 'k6';

const SEARCH_URL = __ENV.SEARCH_URL || 'http://localhost:8080/search';
const CHAT_URL = __ENV.CHAT_URL || 'http://localhost:8000/v1/chat/completions';

export const options = {
  scenarios: {
    search: {
      executor: 'constant-vus',
      vus: 5,
      duration: '30s',
      exec: 'search',
    },
    chat: {
      executor: 'constant-vus',
      vus: 2,
      duration: '30s',
      exec: 'chat',
      startTime: '5s',
    },
  },
  thresholds: {
    'http_req_duration{scenario:search}': ['p(95)<2000'],
    'http_req_duration{scenario:chat}': ['p(95)<15000'],
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
      messages: [{ role: 'user', content: 'hello' }],
      stream: false,
    }),
    { headers: { 'Content-Type': 'application/json' }, tags: { scenario: 'chat' } },
  );
  check(res, { 'chat status 200': (r) => r.status === 200 });
  sleep(1);
}
