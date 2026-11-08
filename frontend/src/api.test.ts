import {afterEach, describe, expect, it, vi} from "vitest";
import {api, ApiError, setCsrf} from "./api";
afterEach(() => { vi.unstubAllGlobals(); setCsrf(null); });
describe("upload transport contract", () => {
  it("sends explicit upload identity with CSRF and the original multipart form", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{"id":"fixture"}', {status:201, headers:{'content-type':'application/json'}}));
    vi.stubGlobal('fetch', fetcher); setCsrf('synthetic-csrf');
    const form = new FormData(); form.append('file',new Blob(['fixture']), 'fixture.pdf');
    expect(await api('/uploads',{form, uploadKey:'synthetic-request-01'})).toEqual({id:'fixture'});
    expect(fetcher).toHaveBeenCalledWith('/api/v1/uploads', expect.objectContaining({
      body:form, credentials:'same-origin', headers:expect.objectContaining({
        'Idempotency-Key':'synthetic-request-01', 'X-CSRF-Token':'synthetic-csrf'})}));
  });
  it.each(['truncated','body-lost','wrong-type'])('treats a %s successful response as uncertain', async kind => {
    const response = new Response(kind==='truncated' ? '{' : '<html>proxy</html>', {
      status:201, headers:{'content-type':kind==='wrong-type' ? 'text/html' : 'application/json'}});
    if (kind==='body-lost') response.json = () => Promise.reject(new TypeError('synthetic connection reset'));
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response));
    await expect(api('/uploads',{form:new FormData(),uploadKey:'synthetic-request-01'}))
      .rejects.toMatchObject({code:'response_unconfirmed', status:0});
  });
  it("preserves uniform server denial instead of retrying it", async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{"error":{"code":"not_found","message":"Not found."}}', {
      status:404,headers:{'content-type':'application/json'}})));
    await expect(api('/uploads/requests/synthetic-request-01')).rejects.toBeInstanceOf(ApiError);
  });
});
