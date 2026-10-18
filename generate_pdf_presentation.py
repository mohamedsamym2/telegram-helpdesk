import os
import subprocess

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Enterprise Telegram IT Support Helpdesk - Solution Proposal</title>
    <style>
        @page {
            size: A4 portrait;
            margin: 10mm 12mm 10mm 12mm;
            @bottom-right {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 8pt;
                color: #94a3b8;
            }
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #0f172a;
            background: #ffffff;
            font-size: 8.5pt;
            line-height: 1.4;
        }
        .page-break {
            page-break-before: always;
        }
        .header-cover {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #312e81 100%);
            color: #ffffff;
            padding: 22px 24px;
            border-radius: 10px;
            margin-bottom: 14px;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
        }
        .badge-cover {
            display: inline-block;
            background: rgba(99, 102, 241, 0.35);
            border: 1px solid rgba(165, 180, 252, 0.5);
            color: #c7d2fe;
            padding: 3px 10px;
            border-radius: 14px;
            font-size: 7.5pt;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            margin-bottom: 8px;
        }
        h1.cover-title {
            font-size: 19pt;
            font-weight: 800;
            line-height: 1.2;
            margin-bottom: 6px;
            color: #ffffff;
        }
        p.cover-subtitle {
            font-size: 9.5pt;
            color: #cbd5e1;
            margin-bottom: 12px;
            line-height: 1.35;
        }
        .cover-meta {
            display: flex;
            justify-content: space-between;
            border-top: 1px solid rgba(255, 255, 255, 0.15);
            padding-top: 10px;
            font-size: 7.5pt;
            color: #cbd5e1;
        }
        .cover-meta span strong {
            color: #ffffff;
        }
        
        h2.section-title {
            font-size: 11.5pt;
            font-weight: 800;
            color: #0f172a;
            border-bottom: 1.5px solid #4f46e5;
            padding-bottom: 3px;
            margin-top: 12px;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }
        p {
            margin-bottom: 6px;
            color: #334155;
            font-size: 8.5pt;
        }
        
        /* Grid layouts */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 10px;
        }
        .grid-3 {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
            margin-bottom: 10px;
        }
        
        .card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 8px 10px;
        }
        .card-accent { border-top: 3px solid #4f46e5; }
        .card-emerald { border-top: 3px solid #10b981; }
        .card-amber { border-top: 3px solid #f59e0b; }
        
        .card h4 {
            font-size: 9pt;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 2px;
        }
        .card p {
            font-size: 7.8pt;
            color: #475569;
            margin-bottom: 0;
            line-height: 1.35;
        }
        
        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 8px 0 10px 0;
            font-size: 8pt;
        }
        th, td {
            padding: 5px 8px;
            border: 1px solid #cbd5e1;
            text-align: left;
        }
        th {
            background: #0f172a;
            color: #ffffff;
            font-weight: 700;
            font-size: 8pt;
        }
        tr:nth-child(even) td {
            background: #f8fafc;
        }
        
        /* Callout boxes */
        .callout-box {
            background: #eef2ff;
            border-left: 3.5px solid #4f46e5;
            padding: 8px 12px;
            border-radius: 0 6px 6px 0;
            margin: 8px 0;
            font-size: 8pt;
            color: #1e1b4b;
            line-height: 1.35;
        }
        .callout-box strong { color: #312e81; }
        
        .callout-success {
            background: #ecfdf5;
            border-left: 3.5px solid #10b981;
            color: #064e3b;
        }
        .callout-success strong { color: #047857; }
        
        ul {
            margin-left: 16px;
            margin-bottom: 6px;
        }
        li {
            font-size: 8pt;
            color: #334155;
            margin-bottom: 2px;
        }
        
        .pill {
            display: inline-block;
            font-size: 7.5pt;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 4px;
        }
        .pill-blue { background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
        .pill-green { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
        .pill-dark { background: #0f172a; color: #ffffff; }

        .footer-note {
            text-align: center;
            font-size: 7.5pt;
            color: #94a3b8;
            margin-top: 14px;
            border-top: 1px solid #e2e8f0;
            padding-top: 6px;
        }
    </style>
</head>
<body>

    <!-- ==================== PAGE 1 ==================== -->
    <div class="header-cover">
        <span class="badge-cover">Enterprise IT Solution Proposal</span>
        <h1 class="cover-title">Telegram IT Support Helpdesk &amp; Incident Management System</h1>
        <p class="cover-subtitle">A high-performance, real-time ticketing platform connecting employees seamlessly via Telegram to an intuitive IT operations command dashboard.</p>
        <div class="cover-meta">
            <span><strong>System Edition:</strong> Version 2.0 (English Edition)</span>
            <span><strong>Target Audience:</strong> Corporate IT Leadership &amp; Operations</span>
            <span><strong>Deployment Models:</strong> On-Premises Windows Server &amp; Cloud VPS</span>
        </div>
    </div>

    <h2 class="section-title">1. Executive Summary</h2>
    <p>Modern enterprises face a persistent dilemma in IT support: traditional helpdesk portals are rarely embraced by staff, leading to unstructured inquiries scattered across personal messaging, casual phone calls, and chaotic email threads. This results in lost requests, breached SLAs, and unmeasurable IT operations.</p>
    
    <p><strong>The Enterprise Telegram Helpdesk</strong> resolves this challenge by meeting employees where they already communicate—on Telegram. Without downloading new applications or remembering separate credentials, staff instantly open tickets, attach screenshots, and receive real-time updates. Concurrently, IT engineers operate from a centralized, high-speed web console featuring live WebSocket event streaming, SLA countdowns, private internal notes, automated knowledge base replies, and customer satisfaction tracking.</p>

    <div class="grid-3">
        <div class="card card-accent">
            <h4>⚡ Zero-Friction Adoption</h4>
            <p>Employees create tickets with zero learning curve by messaging the IT bot or mentioning it in company groups.</p>
        </div>
        <div class="card card-emerald">
            <h4>🔒 Complete Privacy Routing</h4>
            <p>Technician replies and resolution notes are delivered privately to the user's 1-on-1 chat, protecting sensitive data.</p>
        </div>
        <div class="card card-amber">
            <h4>📊 Data-Driven Operations</h4>
            <p>Enforce strict SLAs, capture 5-star customer ratings, and export detailed Excel/CSV incident reports.</p>
        </div>
    </div>

    <h2 class="section-title">2. Problem vs. Solution Analysis</h2>
    <table>
        <thead>
            <tr>
                <th style="width: 20%;">Challenge Area</th>
                <th style="width: 40%;">Traditional Helpdesk (Zendesk / Jira / Email)</th>
                <th style="width: 40%;">Enterprise Telegram IT Helpdesk</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>User Adoption</strong></td>
                <td>Staff forget portal passwords and bypass complex web forms; critical tickets get lost.</td>
                <td>Instant ticket creation directly from Telegram chat or group mentions. Zero login barrier.</td>
            </tr>
            <tr>
                <td><strong>Communication Speed</strong></td>
                <td>Slow email notifications frequently caught in spam filters or buried in inbox clutter.</td>
                <td>Real-time bi-directional messaging with instant push notifications on mobile and desktop.</td>
            </tr>
            <tr>
                <td><strong>Licensing Overhead</strong></td>
                <td>Expensive monthly SaaS fees per technician ($30 to $115 per seat/month).</td>
                <td><strong>Unlimited Technicians &amp; Unlimited Tickets</strong> with zero per-seat monthly penalties.</td>
            </tr>
            <tr>
                <td><strong>Triage &amp; Dispatch</strong></td>
                <td>Manual categorization causes dispatch bottlenecks and delayed engineer assignments.</td>
                <td>Smart auto-categorization (Hardware, Network, ERP, Software, Printers) &amp; SLA risk countdowns.</td>
            </tr>
            <tr>
                <td><strong>Quality &amp; CSAT</strong></td>
                <td>Low survey response rates (<5%) via email links; management lacks actionable CSAT data.</td>
                <td>Interactive 1-to-5 star survey triggered automatically in Telegram chat upon resolution (high response rate).</td>
            </tr>
        </tbody>
    </table>

    <div class="footer-note">Enterprise Telegram IT Support Helpdesk &bull; Confidential Proposal &bull; Section 1 &amp; 2</div>

    <!-- ==================== PAGE 2 ==================== -->
    <div class="page-break"></div>

    <h2 class="section-title">3. Comprehensive Feature Capabilities</h2>
    <div class="grid-2">
        <div class="card card-accent">
            <h4>🖥️ Real-Time IT Command Dashboard</h4>
            <p>Dark-mode enterprise web console with live WebSocket event streaming. New tickets, technician claims, status changes, and incoming messages reflect instantly across all open browser tabs without refreshing.</p>
        </div>
        <div class="card card-accent">
            <h4>💬 Private 1-on-1 Communication Routing</h4>
            <p>When an employee raises an issue inside an IT company group, technician replies route privately into a 1-on-1 chat with the user. Keeps public groups clean while protecting passwords and confidential screenshots.</p>
        </div>
        <div class="card card-accent">
            <h4>⏱️ SLA Management &amp; Breach Alerts</h4>
            <p>Configurable SLA deadlines tailored by priority (Critical: 2h, High: 6h, Medium: 24h, Low: 48h). Visual countdown timers alert dispatchers before breaches occur.</p>
        </div>
        <div class="card card-accent">
            <h4>🔒 Private Internal Team Notes</h4>
            <p>Technicians can annotate tickets with confidential internal notes (e.g. switch ports, IP addresses, root-cause diagnostics) visible exclusively to IT staff and never shared with users.</p>
        </div>
        <div class="card card-accent">
            <h4>⭐ Automated 5-Star CSAT Surveys</h4>
            <p>Upon ticket resolution, an interactive 5-star customer satisfaction survey is automatically pushed to the employee's Telegram chat. Live analytics track technician rating averages and satisfaction trends.</p>
        </div>
        <div class="card card-accent">
            <h4>📚 Self-Service Knowledge Base &amp; Auto-FAQ</h4>
            <p>Built-in keyword-matching FAQ engine that instantly answers repetitive requests (e.g. Wi-Fi credentials, VPN setup, printer drivers) before a technician is needed, deflecting up to 40% of inquiries.</p>
        </div>
    </div>

    <h2 class="section-title">4. Flexible Deployment Architectures</h2>
    <p>To accommodate diverse corporate compliance, security, and infrastructural requirements, the system supports two primary deployment topologies:</p>

    <!-- Option A -->
    <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #10b981; border-radius: 6px; padding: 10px 12px; margin-bottom: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <h3 style="color: #0f172a; font-size: 10pt; font-weight: 800;">OPTION A: On-Premises Windows Server (Corporate Local Network)</h3>
            <span class="pill pill-green">Monthly Hosting Cost: $0.00 / Month</span>
        </div>
        <p><strong>Architecture Concept:</strong> Installed directly inside the company's private local area network (LAN) on an existing Windows Server or dedicated office computer running 24/7 as a silent, background Windows Service.</p>
        
        <p style="margin-bottom: 3px;"><strong>Key Operational Advantages:</strong></p>
        <ul>
            <li><strong>Complete Data Sovereignty:</strong> All incident histories, employee profiles, internal notes, and SQLite databases remain strictly inside the company's private network.</li>
            <li><strong>Zero Monthly Infrastructure Fees:</strong> Leverages existing in-house hardware. No cloud hosting bills, bandwidth fees, or storage charges ($0/mo).</li>
            <li><strong>High-Speed Local Access:</strong> IT technicians access the console locally over LAN/Wi-Fi with ultra-fast sub-10ms response times.</li>
            <li><strong>Silent Background Service:</strong> Operates completely in the background without terminal popups, and auto-starts on system boot.</li>
        </ul>

        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; font-size: 7.5pt; background: #ffffff; padding: 6px 10px; border-radius: 4px; border: 1px solid #e2e8f0; margin-top: 4px;">
            <div><strong>Operating System:</strong><br>Win 10/11 Pro, or Server 2016-2022</div>
            <div><strong>Processor:</strong><br>Dual-Core 2.0 GHz or higher</div>
            <div><strong>RAM Memory:</strong><br>2 GB to 4 GB RAM available</div>
            <div><strong>Network Connectivity:</strong><br>LAN access + outbound HTTPS (port 443)</div>
        </div>
        <p style="font-size: 7.5pt; color: #64748b; margin-top: 4px; margin-bottom: 0;"><em>Operational Requirement: The host machine should stay powered on during business operating hours (or 24/7 if continuous overnight ticketing is desired).</em></p>
    </div>

    <!-- Option B -->
    <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #4f46e5; border-radius: 6px; padding: 10px 12px; margin-bottom: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <h3 style="color: #0f172a; font-size: 10pt; font-weight: 800;">OPTION B: Dedicated Cloud VPS (Hosted Online 24/7)</h3>
            <span class="pill pill-blue">Hosting Provider Cost: ~$4.00 – $6.00 / Month</span>
        </div>
        <p><strong>Architecture Concept:</strong> Deployed on a dedicated, high-availability Cloud Virtual Private Server (VPS) hosted in a certified tier-3 data center, accessible over secure HTTPS from any browser worldwide.</p>
        
        <p style="margin-bottom: 3px;"><strong>Key Operational Advantages:</strong></p>
        <ul>
            <li><strong>Guaranteed 99.9% Uptime:</strong> Operates 24/7/365 without relying on office electricity, backup generators, or local building internet connections.</li>
            <li><strong>Seamless Remote Access:</strong> IT engineers can manage tickets and assist staff from home, mobile devices, or branch offices without requiring a corporate VPN.</li>
            <li><strong>Automated Cloud Backups:</strong> Daily snapshots and database backups executed automatically by the cloud infrastructure provider.</li>
            <li><strong>Zero Hardware Burden:</strong> Eliminates physical PC maintenance, office noise, and server hardware replacement cycles.</li>
        </ul>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; font-size: 7.5pt; background: #ffffff; padding: 6px 10px; border-radius: 4px; border: 1px solid #e2e8f0; margin-top: 4px;">
            <div><strong>VPS Server (Hetzner / DigitalOcean):</strong><br>1 vCPU, 2 GB RAM, 20GB SSD: <strong>~$4.00 to $5.50/mo</strong></div>
            <div><strong>SSL/TLS Certificate:</strong><br>Automated Let's Encrypt SSL: <strong>$0.00 (Free)</strong></div>
            <div><strong>Custom Domain (Optional):</strong><br>e.g. <code>helpdesk.yourcompany.com</code>: <strong>~$10.00/yr</strong></div>
        </div>
    </div>

    <div class="footer-note">Enterprise Telegram IT Support Helpdesk &bull; Confidential Proposal &bull; Section 3 &amp; 4</div>

    <!-- ==================== PAGE 3 ==================== -->
    <div class="page-break"></div>

    <h2 class="section-title">5. Industry Cost Comparison &amp; ROI Analysis</h2>
    <p>Traditional enterprise helpdesk platforms impose aggressive per-agent recurring subscriptions that penalize organizational growth. The Telegram IT Helpdesk model delivers massive cost savings by decoupling licensing from technician seat counts:</p>

    <table>
        <thead>
            <tr>
                <th>Platform / Solution</th>
                <th>Pricing Structure</th>
                <th>Annual Cost (5 IT Agents)</th>
                <th>Annual Cost (15 IT Agents)</th>
                <th>End-User Access Barrier</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Zendesk Suite Team</strong></td>
                <td>$55 / agent / month</td>
                <td>$3,300 / year</td>
                <td>$9,900 / year</td>
                <td>High (Web portal &amp; email verification)</td>
            </tr>
            <tr>
                <td><strong>Jira Service Management</strong></td>
                <td>$22 / agent / month</td>
                <td>$1,320 / year</td>
                <td>$3,960 / year</td>
                <td>Moderate (Atlassian ID required)</td>
            </tr>
            <tr>
                <td><strong>Freshdesk Pro</strong></td>
                <td>$49 / agent / month</td>
                <td>$2,940 / year</td>
                <td>$8,820 / year</td>
                <td>Moderate (Login portal &amp; web forms)</td>
            </tr>
            <tr style="background: #ecfdf5; font-weight: 700;">
                <td style="color: #065f46;"><strong>Enterprise Telegram Helpdesk</strong></td>
                <td style="color: #065f46;"><strong>UNLIMITED AGENTS &amp; TICKETS</strong></td>
                <td style="color: #047857;"><strong>$0 Per-Agent Monthly Fees</strong></td>
                <td style="color: #047857;"><strong>$0 Per-Agent Monthly Fees</strong></td>
                <td style="color: #047857;">Zero (Instant Telegram interface)</td>
            </tr>
        </tbody>
    </table>

    <div class="callout-box callout-success">
        <strong>Return on Investment (ROI) Summary:</strong> By transitioning from conventional per-seat SaaS helpdesk tools to the Enterprise Telegram Helpdesk, an organization saves between <strong>$1,300 and $10,000+ annually</strong> while simultaneously accelerating ticket response times and boosting employee satisfaction.
    </div>

    <h2 class="section-title">6. Rapid 15-Minute Onboarding Roadmap</h2>
    <p>Deployment is turnkey, lightweight, and engineered for zero organizational disruption:</p>

    <div class="grid-2">
        <div class="card card-accent">
            <h4>Phase 1: Bot Activation (5 Minutes)</h4>
            <p>Generate a dedicated corporate Telegram bot token via <code>@BotFather</code>. Configure bot branding (company logo, description, and support contact details).</p>
        </div>
        <div class="card card-accent">
            <h4>Phase 2: Server Provisioning (5 Minutes)</h4>
            <p>Run the 1-click installer on the internal Windows Server (Option A) or deploy to Cloud VPS (Option B). Service initializes silently with clean database.</p>
        </div>
        <div class="card card-accent">
            <h4>Phase 3: Team Configuration (3 Minutes)</h4>
            <p>Access the web console to create technician accounts, customize SLA thresholds, upload company FAQ articles, and link corporate IT group chats.</p>
        </div>
        <div class="card card-accent">
            <h4>Phase 4: Corporate Launch (2 Minutes)</h4>
            <p>Share the bot link (e.g. <code>@Company_ITSupport_Bot</code>) with employees or add the bot to company groups. Ticket intake begins immediately.</p>
        </div>
    </div>

    <h2 class="section-title">7. Security, Privacy &amp; Technical Architecture</h2>
    <div class="grid-3">
        <div class="card">
            <h4>🛡️ Data Security &amp; Isolation</h4>
            <p>Session-based authentication with encrypted cookies, role-based access control (Admin vs Technician), and SQL parameterization preventing injection attacks.</p>
        </div>
        <div class="card">
            <h4>⚡ Ultra-Fast Asynchronous Engine</h4>
            <p>Engineered with Python 3.12 and FastAPI asynchronous I/O. Supports hundreds of concurrent ticket streams with under 15ms local response times.</p>
        </div>
        <div class="card">
            <h4>📦 Zero Database Maintenance</h4>
            <p>Uses SQLite with Write-Ahead Logging (WAL) mode for atomic transactions, high concurrency, and hassle-free, single-file database backup portability.</p>
        </div>
    </div>

    <h2 class="section-title">8. Commercial Engagement &amp; Next Steps</h2>
    <div class="callout-box">
        <strong>Commercial Quotation &amp; Tailored Packaging:</strong><br>
        Commercial proposals, turnkey installation services, and custom enterprise rollout packages are tailored specifically to your organization's scale, infrastructure preferences, and ongoing support requirements.
        <br><br>
        <strong>Next Steps:</strong> Contact our team to schedule a 15-minute live interactive demonstration and receive your customized deployment proposal.
    </div>

    <div class="footer-note">
        Enterprise Telegram IT Support Helpdesk &bull; Confidential Commercial Proposal &bull; Generated October 2026
    </div>

</body>
</html>
"""

html_path = os.path.abspath("IT_Support_Helpdesk_Proposal_Presentation.html")
pdf_path = os.path.abspath("IT_Support_Helpdesk_Proposal_Presentation.pdf")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML saved to: {html_path}")

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(edge_path):
    edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

cmd = [
    edge_path,
    "--headless",
    "--disable-gpu",
    "--no-pdf-header-footer",
    f"--print-to-pdf={pdf_path}",
    html_path
]

res = subprocess.run(cmd, capture_output=True, text=True)
print(f"Edge execution return code: {res.returncode}")
if os.path.exists(pdf_path):
    size = os.path.getsize(pdf_path)
    print(f"SUCCESS: PDF generated at: {pdf_path} (Size: {size} bytes)")
else:
    print(f"ERROR: PDF was not generated. Stderr: {res.stderr}")
