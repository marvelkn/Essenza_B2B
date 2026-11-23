import React, { useMemo, useRef, useState } from 'react';
import {
  FlatList, Keyboard, Modal, Pressable, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import catalogMetadata from '../assets/catalog/compound-metadata.json';
import { compounds, isOutsideDataset } from '../domain/catalog';
import { Icon } from '../ui/Icon';
import { colors, s, sans } from '../ui/theme';

const CAS_QUERY = /^(?:cas\s*:?\s*)?(\d{2,7}-\d{2}-\d)$/i;
const displayName = item => catalogMetadata[item.id]?.displayName ?? item.name;
const casNumber = item => item.cas ?? catalogMetadata[item.id]?.cas;
const identifiers = item => {
  const cas = casNumber(item);
  return [item.cid && `CID ${item.cid}`, cas && `CAS ${cas}`].filter(Boolean).join(' · ');
};
const INDEX = compounds.map(item => ({
  item,
  cas: casNumber(item),
  terms: [displayName(item), item.name, identifiers(item), item.smiles,
    ...item.aliases.filter(alias => !CAS_QUERY.test(alias))].join(' ').toLowerCase(),
}));
const FEATURED = [
  'Vanillin', 'Linalool', 'Geraniol', 'Limonene', 'Eugenol', 'Menthol', 'Citral',
]
  .map(name => compounds.find(item => item.name === name)).filter(Boolean);
const CATALOG_COUNT = compounds.length.toLocaleString('id-ID');

export function CompoundPicker({ selected, onSelect, disabled, targetRef }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [guideOpen, setGuideOpen] = useState(false);
  const listRef = useRef(null);
  const term = query.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!term) return compounds;
    const cas = term.match(CAS_QUERY)?.[1];
    return INDEX.filter(entry => cas ? entry.cas === cas : entry.terms.includes(term))
      .map(entry => entry.item);
  }, [term]);
  const selectedName = selected && displayName(selected);
  const selectedIds = selected && identifiers(selected);
  const selectedOutsideDataset = isOutsideDataset(selected?.smiles);
  const alternateNames = selected && [selected.name, ...selected.aliases]
    .filter(name => name.toLowerCase() !== selectedName.toLowerCase() && !CAS_QUERY.test(name));

  const changeQuery = value => {
    listRef.current?.scrollToOffset({ offset: 0, animated: false });
    setQuery(value);
  };
  const close = () => {
    Keyboard.dismiss();
    setQuery('');
    setGuideOpen(false);
    setOpen(false);
  };
  const select = item => {
    onSelect(item);
    close();
  };

  return <>
    <Pressable
      ref={targetRef}
      accessibilityRole="button"
      accessibilityLabel="Pilih senyawa dari katalog"
      accessibilityHint={selected ? [selectedName, selectedIds, selectedOutsideDataset && 'Di luar dataset']
        .filter(Boolean).join('. ') : undefined}
      accessibilityState={{ disabled, expanded: open }}
      disabled={disabled}
      onPress={() => setOpen(true)}
      style={({ pressed }) => [styles.trigger, selected && styles.selected, pressed && styles.pressed]}
    >
      <View style={styles.triggerIcon}>
        <Icon name={selected ? 'check' : 'search'} size={20} color={colors.green} />
      </View>
      <View style={s.grow}>
        <Text style={styles.triggerName}>{selectedName ?? 'Cari di katalog'}</Text>
        {selectedOutsideDataset && <Text style={styles.outsideDataset}>Di luar dataset</Text>}
        {!!selectedIds && <Text style={styles.identifiers}>{selectedIds}</Text>}
        <Text style={s.small}>{selected ? 'Ganti senyawa' : 'Nama, CID, CAS, atau SMILES'}</Text>
      </View>
      <Icon name="arrow" size={18} color={colors.green} />
    </Pressable>
    {selected && <View>
      {alternateNames.length > 0 && <Text style={s.small}>
        Nama lain · {alternateNames.join(' · ')}
      </Text>}
      {!!selected.structureNote && <Text style={s.small}>{selected.structureNote}</Text>}
      <Text numberOfLines={2} style={s.mono}>{selected.smiles}</Text>
    </View>}
    <Modal visible={open} animationType="slide" onRequestClose={close}>
      <SafeAreaView style={styles.modal}>
        <View style={styles.header}>
          <Text accessibilityRole="header" style={[s.title, s.grow]}>Katalog senyawa</Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Tutup katalog"
            onPress={close}
            style={({ pressed }) => [styles.close, pressed && styles.pressed]}
          ><Icon name="close" /></Pressable>
        </View>
        <View style={styles.search}>
          <Icon name="search" size={19} color={colors.muted} />
          <TextInput
            accessibilityLabel="Cari senyawa dalam katalog"
            value={query}
            onChangeText={changeQuery}
            placeholder="Nama, CID, CAS, atau SMILES"
            placeholderTextColor={colors.muted}
            autoCapitalize="none"
            autoCorrect={false}
            spellCheck={false}
            returnKeyType="search"
            style={styles.searchInput}
          />
          {!!query && <Pressable
            accessibilityRole="button"
            accessibilityLabel="Hapus pencarian"
            onPress={() => changeQuery('')}
            style={styles.iconButton}
          ><Icon name="close" size={18} color={colors.green} /></Pressable>}
        </View>
        <View style={styles.toolbar}>
          <Text accessibilityLiveRegion="polite" style={[s.small, s.grow]}>
            {term ? `${filtered.length.toLocaleString('id-ID')} hasil` : `${CATALOG_COUNT} senyawa`}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Arti tanda pada nama"
            accessibilityState={{ expanded: guideOpen }}
            onPress={() => {
              Keyboard.dismiss();
              setGuideOpen(!guideOpen);
              listRef.current?.scrollToOffset({ offset: 0, animated: false });
            }}
            style={styles.guideButton}
          >
            <Icon name="info" size={16} color={colors.green} />
            <Text style={styles.guideButtonText}>Arti tanda pada nama</Text>
          </Pressable>
        </View>
        <FlatList
          ref={listRef}
          data={filtered}
          keyExtractor={item => String(item.id)}
          keyboardShouldPersistTaps="handled"
          initialNumToRender={16}
          maxToRenderPerBatch={24}
          windowSize={7}
          contentContainerStyle={styles.list}
          ListHeaderComponent={<View>
            {guideOpen && <View style={styles.guide}>
              <Text style={s.label}>(+) dan (−) · Rotasi optik</Text>
              <Text style={s.body}>
                (+) searah jarum jam, (−) berlawanan arah jarum jam. Ini arah putaran cahaya terpolarisasi saat diukur.
              </Text>
              <Text style={s.label}>(2E) dan (2Z) · Posisi gugus di ikatan rangkap</Text>
              <Text style={s.body}>
                Angka 2 menunjukkan ikatan rangkap di antara posisi 2 dan 3.
                E berarti gugus prioritas ada di sisi berlawanan, Z di sisi yang sama.
              </Text>
              <Text style={s.label}>CID dan CAS · Nomor identitas</Text>
              <Text style={s.body}>
                CID menunjuk entri di PubChem. CAS tampil jika nomor tercatat untuk struktur itu di sumber katalog.
              </Text>
            </View>}
            {!term && <View style={styles.quick}>
              <Text style={s.label}>Pilihan cepat</Text>
              <View style={styles.quickRow}>{FEATURED.map(item =>
                <Pressable
                  key={item.id}
                  accessibilityRole="button"
                  accessibilityLabel={`Pilih ${item.name}`}
                  accessibilityState={{ selected: selected?.id === item.id }}
                  onPress={() => select(item)}
                  style={[styles.quickChip, selected?.id === item.id && styles.selected]}
                ><Text style={styles.quickText}>{item.name}</Text></Pressable>)}</View>
            </View>}
          </View>}
          ListEmptyComponent={<View style={[s.center, styles.empty]}>
            <Text style={s.heading}>Senyawa tidak ditemukan</Text>
            <Text style={styles.emptyText}>Coba nama lain atau cari dengan CID, CAS, atau SMILES.</Text>
          </View>}
          renderItem={({ item }) => {
            const name = displayName(item);
            const ids = identifiers(item);
            const cas = casNumber(item);
            const isSelected = selected?.id === item.id;
            const outsideDataset = isOutsideDataset(item.smiles);
            const hint = [name !== item.name && item.name, cas && `CAS ${cas}`,
              outsideDataset && 'Di luar dataset', item.structureNote]
              .filter(Boolean).join('. ');
            return <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Pilih ${name}${item.cid ? `, CID ${item.cid}` : ''}`}
              accessibilityHint={hint || undefined}
              accessibilityState={{ selected: isSelected }}
              onPress={() => select(item)}
              style={({ pressed }) => [styles.row, isSelected && styles.selected, pressed && styles.pressed]}
            >
              <View style={s.grow}>
                <Text style={styles.name}>{name}</Text>
                {outsideDataset && <Text style={styles.outsideDataset}>Di luar dataset</Text>}
                {name !== item.name && <Text style={s.small}>{item.name}</Text>}
                {!!ids && <Text style={styles.identifiers}>{ids}</Text>}
                {!!item.structureNote && <Text style={s.small}>{item.structureNote}</Text>}
                <Text numberOfLines={1} style={styles.structure}>{item.smiles}</Text>
              </View>
              <Icon name={isSelected ? 'check' : 'arrow'}
                size={18} color={isSelected ? colors.green : colors.muted} />
            </Pressable>;
          }}
        />
      </SafeAreaView>
    </Modal>
  </>;
}

const styles = StyleSheet.create({
  trigger: { minHeight: 72, borderWidth: 1, borderColor: colors.line,
    backgroundColor: colors.paper, borderRadius: 16, padding: 12,
    flexDirection: 'row', alignItems: 'center', gap: 12 },
  triggerIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: colors.pale,
    alignItems: 'center', justifyContent: 'center' },
  selected: { borderColor: colors.green, backgroundColor: colors.pale },
  triggerName: { fontFamily: sans, fontSize: 16, fontWeight: '600', color: colors.ink },
  modal: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20,
    paddingTop: 12, paddingBottom: 16, gap: 12 },
  iconButton: { minWidth: 48, minHeight: 48, justifyContent: 'center', alignItems: 'center' },
  close: { minWidth: 48, minHeight: 48, justifyContent: 'center', alignItems: 'center',
    borderWidth: 1, borderColor: colors.line, borderRadius: 16, backgroundColor: colors.paper },
  search: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 20,
    borderWidth: 1, borderColor: colors.line, borderRadius: 16,
    backgroundColor: colors.paper, paddingLeft: 14 },
  searchInput: { flex: 1, minHeight: 50, fontFamily: sans, fontSize: 14,
    color: colors.ink, paddingHorizontal: 10 },
  toolbar: { ...s.between, marginHorizontal: 20, paddingHorizontal: 2, gap: 4 },
  guideButton: { flexDirection: 'row', alignItems: 'center', minHeight: 48, gap: 6,
    flexShrink: 1, paddingLeft: 8 },
  guideButtonText: { ...s.label, color: colors.green, flexShrink: 1 },
  guide: { backgroundColor: colors.pale, borderRadius: 16, padding: 14, gap: 6,
    marginBottom: 12 },
  list: { paddingHorizontal: 20, paddingBottom: 32 },
  quick: { marginBottom: 16, gap: 8 },
  quickRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  quickChip: { minHeight: 48, justifyContent: 'center', backgroundColor: colors.paper,
    borderWidth: 1, borderColor: colors.line, borderRadius: 24,
    paddingHorizontal: 14, paddingVertical: 8 },
  quickText: { ...s.label, color: colors.green },
  row: { minHeight: 72, borderWidth: 1, borderColor: colors.line, borderRadius: 16,
    backgroundColor: colors.paper, flexDirection: 'row', alignItems: 'center',
    paddingVertical: 10, paddingHorizontal: 14, gap: 12, marginBottom: 8 },
  name: { fontFamily: sans, fontSize: 15, fontWeight: '600', color: colors.ink },
  identifiers: { ...s.label, color: colors.green, marginTop: 2 },
  outsideDataset: { ...s.label, color: colors.amber },
  structure: { ...s.mono, color: colors.muted },
  empty: { paddingHorizontal: 12 },
  emptyText: { ...s.body, textAlign: 'center' },
  pressed: { opacity: 0.65 },
});
