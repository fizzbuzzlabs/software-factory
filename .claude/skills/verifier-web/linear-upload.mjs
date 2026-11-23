// Lands verifier-web evidence on a Linear issue via the GraphQL API, so the
// harness attaches it as a mechanical step of the recording run rather than a
// prose instruction the agent can skip. No extra deps: global fetch (Node 18+)
// + node:fs. Personal API keys authenticate with the raw token in the
// Authorization header — Linear rejects a Bearer prefix.
//
// Two landing modes, because Linear renders them differently:
//   - commentVideoToLinear → a comment whose body *embeds* the asset URL, which
//                           Linear renders as a full inline <video> player with
//                           scrub + playback-speed controls. This is the primary
//                           evidence a run lands.
//   - attachToLinear      → attachmentCreate, an attachment *card* — a bare
//                           download link for a video, no player. Used only as
//                           the webm fallback when ffmpeg can't build the mp4.
import { readFile, stat } from 'node:fs/promises'

const ENDPOINT = 'https://api.linear.app/graphql'

async function gql(token, query, variables) {
  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: token },
    body: JSON.stringify({ query, variables }),
  })
  const body = await res.json().catch(() => ({}))
  if (body.errors?.length) throw new Error(body.errors.map((e) => e.message).join('; '))
  return body.data
}

async function resolveIssueId(token, ticket) {
  const { issue } = await gql(token, 'query($id:String!){ issue(id:$id){ id } }', { id: ticket })
  return issue?.id ?? null
}

// Uploads `filePath` and returns its Linear asset URL, ready to reference from an
// attachment or a comment body. Throws on any failure so callers report a note.
async function uploadAsset(token, filePath, filename, contentType) {
  const bytes = await readFile(filePath)
  const { size } = await stat(filePath)
  const { fileUpload } = await gql(
    token,
    `mutation($contentType:String!,$filename:String!,$size:Int!){
      fileUpload(contentType:$contentType,filename:$filename,size:$size){
        success uploadFile { uploadUrl assetUrl headers { key value } }
      }
    }`,
    { contentType, filename, size },
  )
  const upload = fileUpload?.uploadFile
  if (!fileUpload?.success || !upload) throw new Error('fileUpload was not granted')

  const headers = { 'Content-Type': contentType }
  for (const h of upload.headers ?? []) headers[h.key] = h.value
  const put = await fetch(upload.uploadUrl, { method: 'PUT', headers, body: bytes })
  if (!put.ok) throw new Error(`upload PUT ${put.status}`)
  return upload.assetUrl
}

// Uploads `filePath` and creates an attachment on `ticket` (e.g. "ABC-57").
// Returns { ok, url?, note? } and never throws — a Linear hiccup must not fail a
// verification run.
export async function attachToLinear({ token, ticket, filePath, filename, contentType, title, subtitle }) {
  try {
    const issueId = await resolveIssueId(token, ticket)
    if (!issueId) return { ok: false, note: `ticket ${ticket} did not resolve` }

    const assetUrl = await uploadAsset(token, filePath, filename, contentType)
    const { attachmentCreate } = await gql(
      token,
      `mutation($input:AttachmentCreateInput!){
        attachmentCreate(input:$input){ success attachment { url } }
      }`,
      { input: { issueId, url: assetUrl, title, subtitle } },
    )
    if (!attachmentCreate?.success) return { ok: false, note: 'attachmentCreate returned success=false' }
    return { ok: true, url: attachmentCreate.attachment?.url }
  } catch (e) {
    return { ok: false, note: e.message }
  }
}

// Uploads a video and posts a comment that embeds it, so the ticket carries a
// true inline player (scrub + speed) — the primary evidence a run lands. Same
// contract as attachToLinear: returns { ok, url?, note? } and never throws.
export async function commentVideoToLinear({ token, ticket, filePath, filename, contentType, caption }) {
  try {
    const issueId = await resolveIssueId(token, ticket)
    if (!issueId) return { ok: false, note: `ticket ${ticket} did not resolve` }

    const assetUrl = await uploadAsset(token, filePath, filename, contentType)
    // A bare embed on its own line is what Linear turns into a player; the caption
    // rides above it. All of ![](url) / bare-url / [text](url) render as a player
    // (verified) — the image form reads as "media" to a human skimming markdown.
    const body = `${caption}\n\n![${filename}](${assetUrl})`
    const { commentCreate } = await gql(
      token,
      `mutation($input:CommentCreateInput!){
        commentCreate(input:$input){ success comment { url } }
      }`,
      { input: { issueId, body } },
    )
    if (!commentCreate?.success) return { ok: false, note: 'commentCreate returned success=false' }
    return { ok: true, url: commentCreate.comment?.url }
  } catch (e) {
    return { ok: false, note: e.message }
  }
}
