// src/components/data-table.tsx
// One shared TanStack Table wrapper (ReUI data-grid as project-owned source):
// dense rows, horizontal scroll inside the region, record count + pagination
// owned by the DataGrid.

import { useState } from "react"
import {
  DataGrid,
  DataGridContainer,
  dataGridFeatures,
  type DataGridFeatures,
} from "@/components/reui/data-grid/data-grid"
import { DataGridScrollArea } from "@/components/reui/data-grid/data-grid-scroll-area"
import { DataGridTable } from "@/components/reui/data-grid/data-grid-table"
import type {
  ColumnDef,
  PaginationState,
  SortingState,
} from "@tanstack/react-table"
import { useTable } from "@tanstack/react-table"

export function DataTable<Row extends object>({
  data,
  columns,
  initialSorting,
  pageSize = 12,
  getRowId,
}: {
  data: Row[]
  columns: ColumnDef<DataGridFeatures, Row>[]
  initialSorting?: SortingState
  pageSize?: number
  getRowId?: (row: Row) => string
}) {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize,
  })
  const [sorting, setSorting] = useState<SortingState>(initialSorting ?? [])

  const table = useTable({
    features: dataGridFeatures,
    columns,
    data,
    pageCount: Math.max(1, Math.ceil((data?.length ?? 0) / pageSize)),
    getRowId,
    state: { pagination, sorting },
    onPaginationChange: setPagination,
    onSortingChange: setSorting,
  })

  return (
    <DataGrid
      table={table}
      recordCount={data?.length ?? 0}
      tableLayout={{ dense: true }}
    >
      <div className="flex flex-col gap-2">
        <DataGridContainer>
          <DataGridScrollArea>
            <DataGridTable />
          </DataGridScrollArea>
        </DataGridContainer>
      </div>
    </DataGrid>
  )
}
