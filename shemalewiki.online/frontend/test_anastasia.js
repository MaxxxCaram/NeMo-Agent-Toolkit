import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://qtuzpswxzengqoqqwtpt.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || 'sb_publishable_cwSD5GVp927MuLu0N1uROA_z7OsOjIB';
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

async function test() {
    const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', 5131)
        .single();
        
    if (error) {
        console.error('Error:', error);
        
        // Search by name
        console.log('Searching by name...');
        const { data: searchData, error: searchError } = await supabase
            .from('profiles')
            .select('*')
            .ilike('name', '%Anastasia%');
        if (searchError) {
            console.error('Search error:', searchError);
        } else {
            console.log('Search matches:', searchData);
        }
    } else {
        console.log('Anastasia Penny profile:', data);
    }
}

test();
