import PostalMime from 'postal-mime';
import { Buffer } from 'node:buffer';

export default {
	async email(message, env, ctx) {
		const parser = new PostalMime();

		const rawEmailResponse = new Response(message.raw);
		const rawEmailBuffer = await rawEmailResponse.arrayBuffer();
		const parsedEmail = await parser.parse(rawEmailBuffer);

		const messageId = Date.now().toString() + Math.random().toString(36).substring(2, 7);
		let htmlContent = parsedEmail.html || `<p>${parsedEmail.text || 'Tidak ada konten'}</p>`;
		const regularAttachments = [];

		let isSpam = false;

		const authResults = message.headers.get('Authentication-Results') || '';
		if (authResults.includes('dkim=fail') || authResults.includes('spf=fail') || authResults.includes('dmarc=fail')) {
			isSpam = true;
		}

		const spamFlag = message.headers.get('X-Spam-Flag') || '';
		if (spamFlag.toUpperCase() === 'YES') {
			isSpam = true;
		}

		if (parsedEmail.attachments && parsedEmail.attachments.length > 0) {
			for (const att of parsedEmail.attachments) {
				if (!att.content || att.content.byteLength > 4 * 1024 * 1024) continue;

				const base64Data = Buffer.from(att.content).toString('base64');
				const mimeType = att.mimeType || 'application/octet-stream';
				const dataUri = `data:${mimeType};base64,${base64Data}`;
				const cleanCid = att.contentId ? att.contentId.replace(/[<>]/g, '') : null;

				if (cleanCid && htmlContent.includes(`cid:${cleanCid}`)) {
					htmlContent = htmlContent.split(`cid:${cleanCid}`).join(dataUri);
				}

				regularAttachments.push({
					filename: att.filename || `lampiran_${Date.now()}`,
					mimeType: mimeType,
					content: base64Data,
				});
			}
		}

		const emailPayload = {
			id: messageId,
			from: parsedEmail.from?.address || message.from || 'Tanpa Pengirim',
			subject: parsedEmail.subject || '(Tanpa Subjek)',
			html: htmlContent,
			text: parsedEmail.text,
			date: parsedEmail.date || new Date().toISOString(),
			attachments: regularAttachments,
			isSpam: isSpam,
		};

		const key = `inbox:${message.to}:${messageId}`;
		await env.EMAIL_KV.put(key, JSON.stringify(emailPayload), { expirationTtl: 3600 });
	},

	async fetch(request, env, ctx) {
		if (request.method === 'OPTIONS') {
			return new Response(null, {
				headers: {
					'Access-Control-Allow-Origin': '*',
					'Access-Control-Allow-Methods': 'GET, OPTIONS',
					'Access-Control-Allow-Headers': 'Content-Type, x-api-key',
				},
			});
		}

		// Otentikasi opsional menggunakan X-API-Key jika dikonfigurasi di environment
		const expectedApiKey = env.API_KEY || env.X_API_KEY;
		if (expectedApiKey) {
			const clientApiKey = request.headers.get('x-api-key');
			if (clientApiKey !== expectedApiKey) {
				return new Response(JSON.stringify({ error: 'Unauthorized: Invalid API Key' }), {
					status: 401,
					headers: {
						'Content-Type': 'application/json',
						'Access-Control-Allow-Origin': '*',
					},
				});
			}
		}

		const url = new URL(request.url);
		const targetEmail = url.searchParams.get('email');

		if (!targetEmail) {
			return new Response('Parameter email tidak ditemukan', {
				status: 400,
				headers: { 'Access-Control-Allow-Origin': '*' },
			});
		}

		const prefix = `inbox:${targetEmail}:`;
		const list = await env.EMAIL_KV.list({ prefix });

		const emails = [];
		for (const key of list.keys) {
			const data = await env.EMAIL_KV.get(key.name);
			if (data) emails.push(JSON.parse(data));
		}

		emails.sort((a, b) => new Date(b.date) - new Date(a.date));

		return new Response(JSON.stringify(emails), {
			headers: {
				'Content-Type': 'application/json',
				'Access-Control-Allow-Origin': '*',
			},
		});
	},
};
