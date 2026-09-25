#include "@MODULE@.h"

#include "champsim.h"
#include "msl/bits.h"

@MODULE@::@MODULE@(CACHE* cache)
: champsim::modules::replacement(cache), my_counter(cache->NUM_SET * cache->NUM_WAY, 0), NUM_SET(cache->NUM_SET), NUM_WAY(cache->NUM_WAY)
{
}

long @MODULE@::find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                           champsim::address full_addr, access_type type)
{
  long victim_way = 0;
  uint8_t max_val = 0;

  for (long w = 0; w < NUM_WAY; ++w) {
    uint8_t current_val = my_counter.at(set * NUM_WAY + w);
    if (current_val > max_val) {
      max_val = current_val;
      victim_way = w;
    }
  }

  return victim_way;
}

void @MODULE@::update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                        champsim::address victim_addr, access_type type, uint8_t hit)
{
  if (hit) {
    procedure_age_and_reset(set, way);
  }
}

void @MODULE@::replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                      champsim::address victim_addr, access_type type)
{
  procedure_age_and_reset(set, way);
}

void @MODULE@::procedure_age_and_reset(long set, long way)
{
  // each_way: except_touched: true, set: {my_counter: {add: 1}}
  for (long w = 0; w < NUM_WAY; ++w) {
    if (w != way) {
      my_counter.at(set * NUM_WAY + w) = (my_counter.at(set * NUM_WAY + w) + 1) & 0x3;
    }
  }

  // set: {my_counter: {const: 0}}
  if (way < NUM_WAY) {
    my_counter.at(set * NUM_WAY + way) = 0;
  }
}
