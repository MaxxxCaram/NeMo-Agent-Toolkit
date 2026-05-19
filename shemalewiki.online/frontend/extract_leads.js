import { createClient } from '@supabase/supabase-js';
import fs from 'fs';
import path from 'path';

const SUPABASE_URL = 'https://qtuzpswxzengqoqqwtpt.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || 'sb_publishable_cwSD5GVp927MuLu0N1uROA_z7OsOjIB';
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

function decodeHtmlEntities(str) {
    if (!str) return '';
    return str
        .replace(/&#(\d+);/g, (match, dec) => String.fromCharCode(dec))
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&apos;/g, "'")
        .trim();
}

function cleanString(str) {
    if (!str) return '';
    const decoded = decodeHtmlEntities(str);
    return decoded.replace(/"/g, '""').trim();
}

// Strip out URLs, domain names, and paths to prevent URL numerical IDs from matching as phone numbers
function removeUrls(text) {
    if (!text) return '';
    // Matches http/https links and typical domain name links with paths
    const urlRegex = /(https?:\/\/[^\s]+)|([a-zA-Z0-9.-]+\.(?:com|net|org|co|info|biz|me|online|xyz|se|nl|es|de|dk|fr|it|be|ch|at|uk|pl|ru|club|link|vip|agency|ca|us|asia)(?:\/[^\s]*)?)/gi;
    return text.replace(urlRegex, ' ');
}

// Deep regex parsing for emails inside the bio description with trail-cleansing
function extractEmailsFromText(text) {
    if (!text) return [];
    const cleanText = decodeHtmlEntities(text);
    const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}/g;
    const matches = cleanText.match(emailRegex) || [];
    
    return [...new Set(matches.map(e => {
        let clean = e.trim().toLowerCase();
        // Remove trailing words joined without spaces (like "Available", "Incall", "Outcall")
        clean = clean.replace(/(?:available|incall|outcall|whatsapp|twitter|instagram|onlyfans|snapchat|telegram|line|viber|skype|wechat|phone|mail|contact|hot|sexy|thai|versatile|escort).*$/i, '');
        return clean;
    }).filter(Boolean))];
}

// Deep regex parsing for phone numbers after stripping URLs
function extractPhonesFromText(text) {
    if (!text) return [];
    const cleanText = decodeHtmlEntities(text);
    
    // First, strip out all URLs to avoid matching domain IDs
    const textWithoutUrls = removeUrls(cleanText);
    
    // Matches international and local phone sequences
    const phoneRegex = /(?:\+|00)?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,9}/g;
    const matches = textWithoutUrls.match(phoneRegex) || [];
    
    return [...new Set(matches
        .map(p => p.trim())
        .filter(p => {
            const digits = p.replace(/\D/g, '');
            // Real phone numbers contain between 8 and 15 digits
            return digits.length >= 8 && digits.length <= 15;
        })
    )];
}

function formatPhone(phoneStr, bioStr) {
    let phones = [];
    
    // 1. Add standard database phone field if present
    if (phoneStr) {
        let clean = phoneStr.trim();
        if (clean.startsWith('[') && clean.endsWith(']')) {
            try {
                const arr = JSON.parse(clean);
                if (Array.isArray(arr)) {
                    arr.forEach(p => phones.push(decodeHtmlEntities(p).trim()));
                }
            } catch (e) {
                clean.replace(/[\[\]"']/g, '').split(',').forEach(p => phones.push(decodeHtmlEntities(p).trim()));
            }
        } else {
            phones.push(decodeHtmlEntities(clean));
        }
    }
    
    // 2. Extract phones from bio and merge
    if (bioStr) {
        const bioPhones = extractPhonesFromText(bioStr);
        bioPhones.forEach(bp => phones.push(bp));
    }
    
    const uniquePhones = [...new Set(phones.filter(Boolean))];
    return uniquePhones.join(', ');
}

function formatEmail(emailStr, bioStr) {
    let emails = [];
    
    // 1. Add standard database email
    if (emailStr && emailStr.trim() !== '') {
        emails.push(emailStr.trim().toLowerCase());
    }
    
    // 2. Extract emails from bio and merge
    if (bioStr) {
        const bioEmails = extractEmailsFromText(bioStr);
        bioEmails.forEach(be => emails.push(be));
    }
    
    const uniqueEmails = [...new Set(emails.filter(Boolean))];
    
    const filteredEmails = uniqueEmails.filter(e => e !== 'info@shemalewiki.com');
    if (filteredEmails.length > 0) {
        return filteredEmails.join(', ');
    }
    
    return uniqueEmails.join(', ');
}

function parseCountryAndCity(location) {
    if (!location) return { country: 'Unknown', city: 'Unknown' };
    
    const cleanLoc = location.replace(/^DRAFT:\s*/i, '');
    if (cleanLoc.includes('|')) {
        const parts = cleanLoc.split('|').map(p => p.trim());
        if (parts.length >= 3) {
            return { country: parts[1], city: parts[2] };
        } else if (parts.length === 2) {
            return { country: parts[0], city: parts[1] };
        }
    }
    
    return { country: cleanLoc, city: 'Unknown' };
}

async function extractLeads() {
    console.log('Retrieving escort profiles from Supabase...');
    
    let allProfiles = [];
    let page = 0;
    const limit = 1000;
    let hasMore = true;

    while (hasMore) {
        const from = page * limit;
        const to = from + limit - 1;

        const { data, error } = await supabase
            .from('profiles')
            .select('name, email, phone, location, bio')
            .range(from, to);

        if (error) {
            console.error('Error fetching profiles page:', error);
            break;
        }

        if (!data || data.length === 0) {
            hasMore = false;
        } else {
            allProfiles = allProfiles.concat(data);
            console.log(`Fetched page ${page + 1}: ${data.length} profiles.`);
            if (data.length < limit) {
                hasMore = false;
            } else {
                page++;
            }
        }
    }

    console.log(`Successfully fetched ${allProfiles.length} profiles in total.`);

    // Define CSV Headers
    let csvContent = '\uFEFF'; // UTF-8 BOM
    csvContent += '"Nombre","País","Ciudad","Email","Teléfono"\n';

    let count = 0;
    for (const p of allProfiles) {
        const { name, email, phone, location, bio } = p;
        
        const formattedEmail = formatEmail(email, bio);
        const formattedPhone = formatPhone(phone, bio);
        
        const hasEmail = formattedEmail && formattedEmail.trim() !== '';
        const hasPhone = formattedPhone && formattedPhone.trim() !== '';
        
        if (!hasEmail && !hasPhone) {
            continue;
        }

        const { country, city } = parseCountryAndCity(location);
        
        csvContent += `"${cleanString(name)}","${cleanString(country)}","${cleanString(city)}","${cleanString(formattedEmail)}","${cleanString(formattedPhone)}"\n`;
        count++;
    }

    const outputPath = path.resolve('../shemalewiki_leads.csv');
    fs.writeFileSync(outputPath, csvContent, 'utf-8');
    
    console.log(`\nSuccess! Compiled ${count} valid leads with contact details into: ${outputPath}`);
}

extractLeads().catch(err => {
    console.error('Lead extraction crashed:', err);
});
