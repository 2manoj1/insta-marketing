"""
Model Context Protocol (MCP) Server.
Implements JSON-RPC 2.0 MCP standard (tools/list, tools/call, initialize).
Provides stdio and HTTP transports for Claude Desktop, Cursor, Antigravity, and SaaS consumers.
"""
import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

from src.models.brand import BrandContact, BrandOpportunity
from src.models.creator import CreatorProfile
from src.skills.contact_verifier import contact_verifier_skill
from src.skills.deep_bio_link import deep_bio_link_skill
from src.skills.negotiation_pricing import negotiation_pricing_skill
from src.skills.okf_memory import okf_memory_skill
from src.skills.pitch_sequencing import pitch_sequencing_skill
from src.skills.stealth_scraper import stealth_scraper_skill

logger = logging.getLogger(__name__)

MCP_TOOLS_MANIFEST = [
    {
        "name": "scrape_creator_profile",
        "description": "Scrapes public Instagram metrics, bio, follower count, and recent reels for a creator using Playwright stealth emulation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Instagram handle (e.g. 'iva_mana5' or '@iva_mana5')",
                }
            },
            "required": ["username"],
        },
    },
    {
        "name": "deep_brand_enrich",
        "description": "Deep crawls brand websites, Linktree, and contact/collab pages to extract marketing emails and mobile/WhatsApp numbers with zero paid APIs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "website_url": {
                    "type": "string",
                    "description": "Brand website URL or Linktree URL (e.g. 'https://snitch.co.in' or 'linktr.ee/brand')",
                },
                "max_subpages": {
                    "type": "integer",
                    "description": "Maximum contact subpages to check (default 3)",
                    "default": 3,
                },
            },
            "required": ["website_url"],
        },
    },
    {
        "name": "verify_contact_info",
        "description": "Validates RFC 5322 email syntax and standardizes phone numbers into international E.164 format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Candidate marketing/PR email address"},
                "phone": {"type": "string", "description": "Candidate mobile or telephone number"},
            },
        },
    },
    {
        "name": "calculate_rate_card",
        "description": "Computes commercial rate cards and pricing deliverables for UGC video ads and sponsored Reels.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "followers_count": {"type": "integer", "description": "Creator follower count"},
                "niche": {"type": "string", "description": "Content niche (e.g. 'Luxury Travel', 'Tech Accessories', 'Fashion')"},
            },
            "required": ["followers_count"],
        },
    },
    {
        "name": "generate_bespoke_pitch",
        "description": "Drafts a high-converting 3-channel pitch sequence (Email + Instagram DM + WhatsApp outreach) tailored for brand sponsors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "creator_username": {"type": "string", "description": "Creator Instagram handle"},
                "brand_name": {"type": "string", "description": "Target company/brand name"},
                "niche": {"type": "string", "description": "Creator primary niche"},
                "collab_angle": {"type": "string", "description": "Custom content hook or creative concept"},
                "followers_count": {"type": "integer", "description": "Creator follower count", "default": 25000},
                "recipient_email": {"type": "string", "description": "Target marketing email", "default": ""},
                "recipient_phone": {"type": "string", "description": "Target mobile number", "default": ""},
            },
            "required": ["creator_username", "brand_name", "niche", "collab_angle"],
        },
    },
    {
        "name": "okf_query_knowledge",
        "description": "Queries the Open Knowledge Framework (OKF) store for verified Instagram advertisers, emails, and phone numbers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "niche": {"type": "string", "description": "Niche or industry keyword (e.g. 'hospitality', 'fashion', 'skincare')"},
                "location": {"type": "string", "description": "Location filter (e.g. 'Bangalore', 'India')"},
                "limit": {"type": "integer", "description": "Maximum results to return", "default": 5},
            },
        },
    },
    {
        "name": "okf_save_learning",
        "description": "Records verified brand intelligence and advertiser contacts into the persistent Open Knowledge Framework store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brand_name": {"type": "string", "description": "Brand name"},
                "website": {"type": "string", "description": "Brand website URL"},
                "industry": {"type": "string", "description": "Industry or niche"},
                "marketing_email": {"type": "string", "description": "Verified marketing/collab email"},
                "mobile_number": {"type": "string", "description": "Verified mobile or telephone number"},
                "suggested_angle": {"type": "string", "description": "High-performing pitch angle"},
            },
            "required": ["brand_name", "website", "marketing_email"],
        },
    },
    {
        "name": "verify_brand_instagram_page",
        "description": "Scrapes and verifies an official brand Instagram page or PR profile, extracting PR/collab emails, WhatsApp numbers, bio links, and ad probability.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brand_handle": {
                    "type": "string",
                    "description": "Official brand Instagram username or URL (e.g. '@snitch.co.in', '@thetamararesorts', or 'blissclub')",
                }
            },
            "required": ["brand_handle"],
        },
    },
]


class MCPServer:
    """
    Model Context Protocol (MCP) Server implementing JSON-RPC 2.0.
    """

    def __init__(self):
        self.server_name = "insta-marketing-mcp"
        self.server_version = "1.0.0"

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a specific tool by name."""
        if tool_name == "scrape_creator_profile":
            username = arguments.get("username", "iva_mana5")
            res = await stealth_scraper_skill.execute(username, use_sample_fallback=True)
            return res.model_dump()

        elif tool_name == "deep_brand_enrich":
            url = arguments.get("website_url", "")
            subpages = arguments.get("max_subpages", 3)
            return await deep_bio_link_skill.crawl_brand_site(url, max_subpages=subpages)

        elif tool_name == "verify_contact_info":
            email = arguments.get("email")
            phone = arguments.get("phone")
            return contact_verifier_skill.execute(email, phone)

        elif tool_name == "calculate_rate_card":
            followers = arguments.get("followers_count", 25000)
            niche = arguments.get("niche", "lifestyle")
            dummy_profile = CreatorProfile(
                username="creator",
                followers_count=followers,
                niche_categories=[niche],
            )
            return negotiation_pricing_skill.calculate_rate_card(dummy_profile, niche_hint=niche)

        elif tool_name == "generate_bespoke_pitch":
            creator_u = arguments.get("creator_username", "creator")
            brand = arguments.get("brand_name", "Brand")
            niche = arguments.get("niche", "lifestyle")
            angle = arguments.get("collab_angle", "UGC Reel feature")
            followers = arguments.get("followers_count", 25000)
            email = arguments.get("recipient_email", f"collab@{brand.lower().replace(' ', '')}.com")
            phone = arguments.get("recipient_phone", "")

            dummy_profile = CreatorProfile(
                username=creator_u,
                full_name=creator_u.capitalize(),
                followers_count=followers,
                niche_categories=[niche],
            )
            opp = BrandOpportunity(
                brand_name=brand,
                website=f"https://{brand.lower().replace(' ', '')}.com",
                industry=niche,
                fit_score=95,
                suggested_angle=angle,
                contact=BrandContact(
                    contact_email=email,
                    mobile_number=phone,
                    phone_number=phone,
                ),
            )
            return pitch_sequencing_skill.generate_sequence(dummy_profile, opp)

        elif tool_name == "okf_query_knowledge":
            niche = arguments.get("niche")
            location = arguments.get("location")
            limit = arguments.get("limit", 5)
            return okf_memory_skill.query(niche=niche, location=location, limit=limit)

        elif tool_name == "okf_save_learning":
            brand = BrandOpportunity(
                brand_name=arguments["brand_name"],
                website=arguments["website"],
                industry=arguments.get("industry", "Lifestyle"),
                suggested_angle=arguments.get("suggested_angle", "Bespoke ad hook"),
                contact=BrandContact(
                    contact_email=arguments["marketing_email"],
                    mobile_number=arguments.get("mobile_number"),
                    phone_number=arguments.get("mobile_number"),
                    source="mcp_save_learning",
                ),
            )
            success = okf_memory_skill.learn(brand)
            return {"success": success, "brand_name": brand.brand_name}

        elif tool_name == "verify_brand_instagram_page":
            handle = arguments.get("brand_handle", "")
            from src.browser.scraper import creator_scraper
            return await creator_scraper.scrape_brand_page(handle)

        else:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

    async def handle_jsonrpc_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Handles a single JSON-RPC 2.0 request."""
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": self.server_name,
                        "version": self.server_version,
                    },
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                },
            }

        elif method == "notifications/initialized":
            return {"jsonrpc": "2.0", "result": {}}

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": MCP_TOOLS_MANIFEST,
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                res = await self.execute_tool(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res, indent=2) if isinstance(res, (dict, list)) else str(res),
                            }
                        ],
                        "isError": False,
                    },
                }
            except Exception as e:
                logger.error(f"Error in tools/call {tool_name}: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error executing tool {tool_name}: {str(e)}"}
                        ],
                        "isError": True,
                    },
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    async def run_stdio(self):
        """Standard stdio transport loop for Model Context Protocol."""
        sys.stderr.write(f"Starting {self.server_name} v{self.server_version} MCP stdio server...\n")
        sys.stderr.flush()

        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                raw_str = line.decode("utf-8").strip()
                if not raw_str:
                    continue

                req = json.loads(raw_str)
                resp = await self.handle_jsonrpc_request(req)
                if resp:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                sys.stderr.write(f"MCP stdio error: {e}\n")
                sys.stderr.flush()


mcp_server = MCPServer()
