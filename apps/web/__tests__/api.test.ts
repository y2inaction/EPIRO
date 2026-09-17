import {
  getEvidence,
  getStory,
  listEvidence,
  listQuestions,
  listStories,
  search,
} from '@/lib/api'

const ORIGINAL_FETCH = global.fetch

function mockJson(body: unknown, status = 200) {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
  global.fetch = fetchMock as unknown as typeof fetch
  return fetchMock
}

function requestedUrl(fetchMock: jest.Mock): string {
  return fetchMock.mock.calls[0][0] as string
}

afterEach(() => {
  global.fetch = ORIGINAL_FETCH
  jest.restoreAllMocks()
})

describe('endpoint targeting', () => {
  it('only ever calls the public API', async () => {
    // The portal must not be able to reach an authenticated endpoint even by
    // mistake: every path goes through the same /api/v1/public prefix.
    const calls: string[] = []
    const fetchMock = jest.fn().mockImplementation((url: string) => {
      calls.push(url)
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) })
    })
    global.fetch = fetchMock as unknown as typeof fetch

    await listStories()
    await listEvidence()
    await listQuestions()
    await getStory('abc')
    await getEvidence('EV-2026-000001')
    await search('borehole')

    expect(calls).toHaveLength(6)
    for (const url of calls) {
      expect(url).toContain('/api/v1/public/')
    }
  })

  it('never sends an authorization header', async () => {
    const fetchMock = mockJson({})

    await listStories()

    const init = fetchMock.mock.calls[0][1] as RequestInit
    const headers = init.headers as Record<string, string>
    expect(Object.keys(headers).map((k) => k.toLowerCase())).not.toContain('authorization')
  })
})

describe('paging', () => {
  it('turns a page number into a skip', async () => {
    const fetchMock = mockJson({ data: [] })

    await listStories({ page: 3, pageSize: 10 })

    expect(requestedUrl(fetchMock)).toContain('skip=20')
    expect(requestedUrl(fetchMock)).toContain('limit=10')
  })

  it('treats page zero and negatives as the first page', async () => {
    const fetchMock = mockJson({ data: [] })

    await listStories({ page: -4, pageSize: 10 })

    expect(requestedUrl(fetchMock)).toContain('skip=0')
  })

  it('omits filters that were not set', async () => {
    const fetchMock = mockJson({ data: [] })

    await listStories({ page: 1 })

    expect(requestedUrl(fetchMock)).not.toContain('language=')
    expect(requestedUrl(fetchMock)).not.toContain('organisation_id=')
  })

  it('passes the filters that were set', async () => {
    const fetchMock = mockJson({ data: [] })

    await listStories({ language: 'ha', featuredOnly: true })

    expect(requestedUrl(fetchMock)).toContain('language=ha')
    expect(requestedUrl(fetchMock)).toContain('featured_only=true')
  })
})

describe('encoding', () => {
  it('escapes a reference so it cannot break out of the path', async () => {
    const fetchMock = mockJson({})

    await getEvidence('../../internal/secret')

    expect(requestedUrl(fetchMock)).not.toContain('../')
  })

  it('escapes a search term', async () => {
    const fetchMock = mockJson({})

    await search('borehole & clinic')

    expect(requestedUrl(fetchMock)).toContain('q=borehole+%26+clinic')
  })
})

describe('failure handling', () => {
  it('reports an unreachable service rather than an empty result', async () => {
    // An empty list would tell a reader that a body has published nothing,
    // which is a different and false claim.
    global.fetch = jest.fn().mockRejectedValue(new Error('ECONNREFUSED')) as unknown as typeof fetch

    const result = await listStories()

    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.status).toBeNull()
      expect(result.message).toContain('could not be reached')
    }
  })

  it('distinguishes a 404 so a page can render not-found', async () => {
    mockJson(null, 404)

    const result = await getStory('missing')

    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.status).toBe(404)
    }
  })

  it('reports a server error', async () => {
    mockJson(null, 503)

    const result = await listEvidence()

    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.status).toBe(503)
    }
  })

  it('survives a body that is not json', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('Unexpected token')
      },
    }) as unknown as typeof fetch

    const result = await listStories()

    expect(result.ok).toBe(false)
  })

  it('returns the payload on success', async () => {
    mockJson({ total: 1, page: 1, page_size: 12, total_pages: 1, data: [{ id: 'a' }] })

    const result = await listStories()

    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.value.total).toBe(1)
      expect(result.value.data).toHaveLength(1)
    }
  })
})
