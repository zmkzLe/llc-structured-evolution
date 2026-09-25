#include "@MODULE@.h"

#include <algorithm>
#include <cmath>

#include "champsim.h"
#include "msl/bits.h"

@MODULE@::@MODULE@(CACHE* cache)
: champsim::modules::replacement(cache), etr(cache->NUM_SET * cache->NUM_WAY, 0),
  rdp(RDP_ENTRIES), NUM_SET(cache->NUM_SET), NUM_WAY(cache->NUM_WAY)
{
}

long @MODULE@::find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                           champsim::address full_addr, access_type type)
{
  long victim_way = 0;
  long max_abs_etr = 0;

  for (long w = 0; w < NUM_WAY; ++w) {
    int8_t current_etr = etr.at(set * NUM_WAY + w);
    long current_abs_etr = std::abs(current_etr);

    if (current_abs_etr > max_abs_etr) {
      max_abs_etr = current_abs_etr;
      victim_way = w;
    } else if (current_abs_etr == max_abs_etr) {
      if (current_etr < 0) {
        victim_way = w;
      }
    }
  }

  return victim_way;
}

void @MODULE@::update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                        champsim::address victim_addr, access_type type, uint8_t hit)
{
  if (hit) {
    if (type == access_type::WRITE) {
      return; // stop
    }

    if (way < NUM_WAY) {
      uint64_t sig = get_pc_sig(ip, true, type);
      auto rdp_entry = rdp_read(sig);

      if (!rdp_entry.valid) {
        etr.at(set * NUM_WAY + way) = 0;
        return; // stop
      }
      etr.at(set * NUM_WAY + way) = rdp_entry.value / 8;
    }
  }
}

void @MODULE@::replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                      champsim::address victim_addr, access_type type)
{
  if (type == access_type::WRITE) {
    if (way < NUM_WAY) {
      etr.at(set * NUM_WAY + way) = -ETR_MAX_ABS;
    }
    return; // stop
  }

  if (way < NUM_WAY) {
    uint64_t sig = get_pc_sig(ip, false, type);
    auto rdp_entry = rdp_read(sig);

    if (!rdp_entry.valid) {
      etr.at(set * NUM_WAY + way) = 8;
      return; // stop
    }
    etr.at(set * NUM_WAY + way) = rdp_entry.value / 8;
  }
}

uint64_t @MODULE@::murmur_hash(uint64_t val) const
{
  val = val ^ (val >> 33);
  val = val * 0xff51afd7ed558ccdULL;
  val = val ^ (val >> 33);
  val = val * 0xc4ceb9fe1a85ec53ULL;
  val = val ^ (val >> 33);
  return val;
}

uint64_t @MODULE@::get_pc_sig(champsim::address ip, bool hit, access_type type) const
{
  uint64_t val = ip.to<uint64_t>();
  val = (val << 1) | (hit ? 1 : 0);
  val = (val << 1) | (type == access_type::PREFETCH ? 1 : 0);
  val = murmur_hash(val);
  return val & ((1 << PC_SIG_BITS) - 1);
}

@MODULE@::rdp_entry_t @MODULE@::rdp_read(uint64_t index) const
{
  return rdp.at(index);
}
