#ifndef REPLACEMENT_@MODULE@_H
#define REPLACEMENT_@MODULE@_H

#include <vector>
#include <cstdint>
#include "cache.h"
#include "modules.h"

class @MODULE@ : public champsim::modules::replacement {
    long NUM_SET;
    long NUM_WAY;

    struct line_state {
        int8_t etr = 0;
    };
    std::vector<std::vector<line_state>> state_per_line;

    struct set_state {
        uint8_t etr_clock = 8;
        uint8_t set_clock = 0;
    };
    std::vector<set_state> state_per_set;

    struct rdp_entry {
        bool valid = false;
        uint8_t value = 0;
    };
    std::vector<rdp_entry> rdp;

    struct sampler_entry {
        bool valid = false;
        uint16_t tag = 0;
        uint16_t signature = 0;
        uint8_t timestamp = 0;
    };
    std::vector<std::vector<sampler_entry>> sampled_cache;
    std::vector<long> sampled_set_to_group;

    uint64_t pc_sig(champsim::address ip, bool hit, bool prefetch);
    int8_t add_etr(int8_t val, int addend);
    uint8_t add_etr_clock(uint8_t val, int addend);
    uint8_t add_set_clock(uint8_t val, int addend);
    uint8_t calc_age(uint8_t clock, uint8_t stamp);
    void train_rdp_toward(uint16_t index, uint8_t sample, int scale, int min_diff);
    void train_rdp_increment(uint16_t index);
    void do_sample_sampled_cache(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, access_type type, bool hit);
    void run_access(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, access_type type, bool hit);

public:
    explicit @MODULE@(CACHE* cache);
    long find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip, champsim::address full_addr, access_type type);
    void replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr, access_type type);
    void update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr, access_type type, uint8_t hit);
};

#endif
