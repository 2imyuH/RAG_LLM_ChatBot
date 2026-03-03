import nodemailer from 'nodemailer';
import dotenv from 'dotenv';

dotenv.config();

/**
 * Creates a configured nodemailer transporter.
 * Automatically falls back to Ethereal Email (fake SMTP) if no real SMTP config is provided in .env.
 */
async function createTransporter() {
    let host = process.env.SMTP_HOST;
    let port = process.env.SMTP_PORT ? parseInt(process.env.SMTP_PORT) : 587;
    let user = process.env.SMTP_USER;
    let pass = process.env.SMTP_PASS;

    // Use test account if no real SMTP is provided
    if (!host || !user || !pass) {
        console.log('[EmailService] No SMTP credentials found in .env. Creating test Ethereal account...');
        const testAccount = await nodemailer.createTestAccount();
        host = 'smtp.ethereal.email';
        port = 587;
        user = testAccount.user;
        pass = testAccount.pass;

        console.log(`[EmailService] 📧 Ethereal Test Account Created: ${user} / ${pass}`);
    }

    return nodemailer.createTransport({
        host,
        port,
        secure: port === 465, // true for 465, false for other ports
        auth: {
            user,
            pass,
        },
    });
}

/**
 * Sends a 6-digit OTP verification email.
 * @param {string} toEmail - The recipient's email address.
 * @param {string} otpCode - The 6-digit OTP code to send.
 */
export async function sendPasswordResetOTP(toEmail, otpCode) {
    try {
        const transporter = await createTransporter();

        const mailOptions = {
            from: '"Brotex R&D AI" <no-reply@brotex.com>',
            to: toEmail,
            subject: 'Brotex - Password Reset Verification Code',
            html: `
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h2 style="color: #2563eb; margin: 0;">Brotex R&D AI</h2>
                    </div>
                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px;">
                        <h3 style="color: #1e293b; margin-top: 0;">Password Reset Request</h3>
                        <p style="color: #475569; line-height: 1.5;">We received a request to reset your password. Please use the following 6-digit verification code to proceed.</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #0f172a; padding: 15px 30px; background-color: #e2e8f0; border-radius: 8px;">${otpCode}</span>
                        </div>
                        
                        <p style="color: #64748b; font-size: 14px; text-align: center;">This code will expire in 10 minutes.</p>
                        <p style="color: #dc2626; font-size: 13px; text-align: center;">If you didn't request this, you can safely ignore this email.</p>
                    </div>
                </div>
            `,
        };

        const info = await transporter.sendMail(mailOptions);

        console.log(`[EmailService] OTP Email sent to ${toEmail}`);

        // If using Ethereal, log the preview URL so the developer can see the fake email
        if (info.messageId && nodemailer.getTestMessageUrl(info)) {
            console.log(`[EmailService] 🌐 Preview Email: ${nodemailer.getTestMessageUrl(info)}`);
        }

        return { success: true, messageId: info.messageId };

    } catch (error) {
        console.error('[EmailService] Failed to send email:', error);
        throw new Error('Failed to send verification email');
    }
}

export default { sendPasswordResetOTP };
