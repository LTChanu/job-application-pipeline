import type { NextApiRequest, NextApiResponse } from 'next';
import { IncomingForm, File as FormidableFile } from 'formidable';
import { promises as fsPromises } from 'fs';
import AWS from 'aws-sdk';
import { mkdir } from 'fs/promises';

export const config = {
    api: { bodyParser: false },
};

const s3 = new AWS.S3({
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
    region: 'eu-north-1', //us-east-1',
});

// Update FormParseResult to handle possible undefined values
type FormParseResult = [
    { [key: string]: string | string[] | undefined },
    { [key: string]: FormidableFile[] | undefined }
];

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const isWindows = process.platform === 'win32';
    const uploadDir = isWindows ? './tmp' : '/tmp';

    if (isWindows) {
        await mkdir(uploadDir, { recursive: true });
    }

    const form = new IncomingForm({
        uploadDir,
        keepExtensions: true,
        multiples: false,
    });

    try {
        const [fields, files]: FormParseResult = await new Promise<FormParseResult>((resolve, reject) => {
            form.parse(req, (err, fields, files) => {
                if (err) reject(err);
                else resolve([fields, files]);
            });
        });

        console.log('Fields:', fields);
        console.log('Files:', files);

        // Add null check since files.cv could be undefined
        const file = files.cv?.[0];
        if (!file || !file.filepath) {
            throw new Error('No CV file uploaded or filepath is undefined');
        }

        const fileBuffer = await fsPromises.readFile(file.filepath);

        const uploadParams = {
            Bucket: 'job-application-cvs-metana',
            Key: `${Date.now()}-${file.originalFilename || 'uploaded-file'}`,
            Body: fileBuffer,
            Metadata: {  // Add form fields as metadata
                name: Array.isArray(fields.name) ? fields.name[0] : fields.name || 'Unknown',
                email: Array.isArray(fields.email) ? fields.email[0] : fields.email || 'Unknown',
                phone: Array.isArray(fields.phone) ? fields.phone[0] : fields.phone || 'Unknown',
            },
            //ACL: 'public-read',
        };

        const result = await s3.upload(uploadParams).promise();
        res.status(200).json({ cvUrl: result.Location, fields });
    } catch (error) {
        console.error('Error processing upload:', error);
        res.status(500).json({ error: 'Failed to process the upload' });
    }
}