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

function formatPhone(phoneStr) {
    if (!phoneStr) return '';
    let clean = phoneStr.trim();
    if (clean.startsWith('[') && clean.endsWith(']')) {
        try {
            const arr = JSON.parse(clean);
            if (Array.isArray(arr)) {
                return arr.map(p => decodeHtmlEntities(p).trim()).filter(Boolean).join(', ');
            }
        } catch (e) {
            // fallback if it's not valid JSON
            return clean.replace(/[\[\]"']/g, '').split(',').map(p => decodeHtmlEntities(p).trim()).filter(Boolean).join(', ');
        }
    }
    return decodeHtmlEntities(clean);
}

function parseCountryAndCity(location) {
    if (!location) return { country: 'Unknown', city: 'Unknown' };
    
    // Check if location format is like "DRAFT: Continent | Country | City" or "Continent | Country | City"
    const cleanLoc = location.replace(/^DRAFT:\s*/i, '');
    if (cleanLoc.includes('|')) {
        const parts = cleanLoc.split('|').map(p => p.trim());
        if (parts.length >= 3) {
            // "Continent | Country | City" -> parts[1] is country, parts[2] is city
            return { country: parts[1], city: parts[2] };
        } else if (parts.length === 2) {
            // "Country | City" -> parts[0] is country, parts[1] is city
            return { country: parts[0], city: parts[1] };
        }
    }
    
    // Fallback if it's a simple string like "Germany" or "Spain"
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
            .select('name, email, phone, location')
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
    // Format: Nombre, Pais, Ciudad, Email, Telefono
    let csvContent = '\uFEFF'; // UTF-8 BOM for perfect Excel encoding on Spanish operating systems
    csvContent += '"Nombre","País","Ciudad","Email","Teléfono"\n';

    let count = 0;
    for (const p of allProfiles) {
        const { name, email, phone, location } = p;
        
        // Skip profiles that don't have ANY contact details
        const hasEmail = email && email.trim() !== '';
        const hasPhone = phone && phone.trim() !== '';
        
        if (!hasEmail && !hasPhone) {
            continue;
        }

        const { country, city } = parseCountryAndCity(location);
        const formattedPhone = formatPhone(phone);
        
        csvContent += `"${cleanString(name)}","${cleanString(country)}","${cleanString(city)}","${cleanString(email)}","${cleanString(formattedPhone)}"\n`;
        count++;
    }

    const outputPath = path.resolve('../shemalewiki_leads.csv');
    fs.writeFileSync(outputPath, csvContent, 'utf-8');
    
    console.log(`\nSuccess! Compiled ${count} valid leads with contact details into: ${outputPath}`);
}

extractLeads().catch(err => {
    console.error('Lead extraction crashed:', err);
});
